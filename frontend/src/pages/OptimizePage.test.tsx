import { describe, it, expect, vi, beforeEach } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { OptimizePage } from './OptimizePage'

const listDatasetsMock = vi.fn()
const getDatasetMock = vi.fn()
const optimizeBatchMock = vi.fn()
const optimizeSeparateMock = vi.fn()
const optimizeSeparateBreaksMock = vi.fn()
const applySeparateBreaksMock = vi.fn()
const createScenarioMock = vi.fn()
const listScenariosMock = vi.fn()
const getAnalysisMock = vi.fn()

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getDataset: (...args: unknown[]) => getDatasetMock(...args),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

vi.mock('../api/optimization', () => ({
  optimize: vi.fn(),
  optimizeBatch: (...args: unknown[]) => optimizeBatchMock(...args),
  optimizeSeparate: (...args: unknown[]) => optimizeSeparateMock(...args),
  optimizeSeparateBreaks: (...args: unknown[]) => optimizeSeparateBreaksMock(...args),
  applySeparateBreaks: (...args: unknown[]) => applySeparateBreaksMock(...args),
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

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: vi.fn(),
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
  optimizeSeparateMock.mockReset()
  optimizeSeparateBreaksMock.mockReset()
  applySeparateBreaksMock.mockReset()
  createScenarioMock.mockReset()
  listScenariosMock.mockReset()
  getAnalysisMock.mockReset()
  listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
  getDatasetMock.mockResolvedValue({ dataset })
  optimizeBatchMock.mockResolvedValue({ results: [row] })
  listScenariosMock.mockResolvedValue({ scenarios: [] })
  getAnalysisMock.mockResolvedValue({
    analysis: { id: 7, queue_setup: { queue_structure: 'shared_queue', queue_ids: [] } },
  })
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

  it('does not fabricate a staffing insight from INVALID_INPUT rows', async () => {
    optimizeBatchMock.mockResolvedValue({ results: [{ ...row,
      lambda_: 5, mu: 4, c_current: 1, c_optimal: null,
      rho_current: null, rho_optimal: null, Wq_current: null, Wq_optimal: null,
      Lq_current: null, Lq_optimal: null, cost_current: null, cost_optimal: null,
      delta_cost: null, delta_Wq: null, delta_Lq: null, delta_c: null, delta_rho: null,
      waiting_cost_current: null, waiting_cost_optimal: null,
      abandonment_cost_current: null, abandonment_cost_optimal: null,
      cost_per_server: null, current_stable: false, optimized_stable: false,
      feasibility_status: 'INVALID_INPUT', warning: 'Optimization is not supported.' }] })
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText('Optimization is not supported.')).toBeInTheDocument()
    expect(screen.queryByText('Staffing Reduction Possible')).not.toBeInTheDocument()
    expect(screen.queryByText('Staffing Increase Recommended')).not.toBeInTheDocument()
    expect(screen.queryByText(/service points/)).not.toBeInTheDocument()
  })

  it('renders same-time queues as distinct rows without key collisions', async () => {
    const errors: unknown[][] = []
    const spy = vi.spyOn(console, 'error').mockImplementation((...args: unknown[]) => { errors.push(args) })
    try {
      optimizeBatchMock.mockResolvedValue({ results: [
        { ...row, lambda_: 5, c_optimal: null, rho_optimal: null, cost_optimal: null, delta_c: null },
        { ...row, lambda_: 9, c_optimal: null, rho_optimal: null, cost_optimal: null, delta_c: null },
      ] })
      const user = userEvent.setup()
      renderWithProviders(<OptimizePage />, { route: '/optimize' })
      await screen.findByRole('option', { name: 'sample' })
      await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
      await user.click(screen.getByRole('button', { name: 'Optimize' }))
      expect(await screen.findByText('5.00 → 5.00')).toBeInTheDocument()
      expect(screen.getByText('9.00 → 9.00')).toBeInTheDocument()
      expect(errors.flat().join(' ')).not.toMatch(/same key/)
    } finally {
      spy.mockRestore()
    }
  })

  it('keeps the genuine staffing insight for complete rows', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('401.31')
    expect(screen.getByText('Staffing Increase Recommended')).toBeInTheDocument()
    expect(screen.getByText(/increasing from 3 to 4 service points/)).toBeInTheDocument()
  })

  it('announces the available-pool coverage notice as a live status', async () => {
    const user = userEvent.setup()
    renderWithProviders(<OptimizePage />, { route: '/optimize' })
    await screen.findByRole('option', { name: 'sample' })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('401.31')
    await user.type(screen.getByLabelText('Available cashiers today'), '10')
    const notice = await screen.findByText('Available pool can cover the optimized schedule.')
    expect(notice.closest('[role="status"]')).not.toBeNull()
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

describe('separate staffing optimization', () => {
  function renderSeparate() {
    getAnalysisMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues', queue_ids: ['lane-a', 'lane-b'] } },
    })
    return renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/optimize" element={<OptimizePage />} />
      </Routes>,
      { route: '/analyses/7/optimize' },
    )
  }

  const candidate = (lanes: number, status: string, util: number | null, cost: number | null) => ({
    active_lane_count: lanes,
    status,
    reason: status === 'FEASIBLE' ? null : `${status} reason`,
    candidate_utilization: util,
    total_cost: cost,
    mean_total_cost: cost,
    server_cost: cost === null ? null : 174,
    waiting_cost: cost === null ? null : cost - 174,
    evaluation_method: 'DES_REPLICATIONS',
  })

  const completeSchedule = {
    schedule: {
      overall: 'COMPLETE',
      reason: null,
      target_utilization: 0.7,
      evaluation_method: 'DES_REPLICATIONS',
      des: { replications: 5, base_seed: 42, duration_hours: 24, max_events: 10000 },
      periods: [
        {
          time: '08:00',
          overall: 'OPTIMAL',
          reason: null,
          current_active_lanes: ['lane-a', 'lane-b'],
          optimal_active_lanes: 1,
          adjustment: -1,
          evaluation_method: 'DES_REPLICATIONS',
          replication_seeds: [42, 43, 44, 45, 46],
          optimum: {
            active_lane_count: 1, recommendation: 'REDUCE', total_cost: 120.5,
            candidate_utilization: 0.6, estimated_optimal: true,
            cost_uncertainty: { mean: 120.5, sd: 4.0, se: 1.8, ci_lower: 115.5, ci_upper: 125.5, n: 5 },
          },
          candidates: [candidate(1, 'FEASIBLE', 0.6, 120.5), candidate(2, 'FEASIBLE', 0.35, 210.0)],
        },
      ],
    },
  }

  it('shows a 40-90 utilization target slider defaulting to 70%', async () => {
    renderSeparate()
    await screen.findByRole('heading', { name: 'Optimize Staffing Schedule' })
    const slider = screen.getByRole('slider', { name: /utilization target/i })
    expect(slider).toHaveAttribute('min', '0.4')
    expect(slider).toHaveAttribute('max', '0.9')
    expect(slider).toHaveValue('0.7')
    expect(screen.queryByTestId('optimize-staffing-blocked')).not.toBeInTheDocument()
  })

  it('describes full coverage as a schedule check, not a lane-count search', async () => {
    renderSeparate()
    await screen.findByRole('heading', { name: 'Optimize Staffing Schedule' })
    expect(screen.getByText(/full coverage/i)).toBeInTheDocument()
    expect(screen.queryByText(/decides how many/i)).not.toBeInTheDocument()
  })

  it('runs one separate optimization and renders the estimated schedule', async () => {
    const user = userEvent.setup()
    optimizeSeparateMock.mockResolvedValue(completeSchedule)
    renderSeparate()
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText('Estimated Optimal Plan')).toBeInTheDocument()
    expect(screen.getByText('Replicated DES')).toBeInTheDocument()
    expect(optimizeSeparateMock).toHaveBeenCalledTimes(1)
    expect(optimizeSeparateMock).toHaveBeenCalledWith(
      7, 1, expect.objectContaining({ target_utilization: 0.7 }),
    )
    expect(screen.getByRole('rowheader', { name: '08:00' })).toBeInTheDocument()
  })

  it('shows the blocked reason and keeps save disabled without an optimum', async () => {
    const user = userEvent.setup()
    optimizeSeparateMock.mockResolvedValue({
      schedule: {
        ...completeSchedule.schedule,
        overall: 'BLOCKED',
        reason: 'Period(s) 08:00 cannot claim an optimum: evidence missing.',
        periods: [{ ...completeSchedule.schedule.periods[0], overall: 'UNSUPPORTED', optimal_active_lanes: null, adjustment: null, optimum: null }],
      },
    })
    renderSeparate()
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText(/cannot claim an optimum/)).toBeInTheDocument()
    await user.type(screen.getByLabelText('Scenario name'), 'blocked plan')
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(createScenarioMock).not.toHaveBeenCalled()
  })

  it('renders missing optima as em-dash rather than zero', async () => {
    const user = userEvent.setup()
    optimizeSeparateMock.mockResolvedValue({
      schedule: {
        ...completeSchedule.schedule,
        overall: 'INFEASIBLE',
        reason: 'Period 08:00 evaluated without a feasible lane count.',
        periods: [{
          ...completeSchedule.schedule.periods[0],
          overall: 'INFEASIBLE', optimal_active_lanes: null, adjustment: null, optimum: null,
          candidates: [candidate(1, 'INFEASIBLE', 0.91, null), candidate(2, 'INFEASIBLE', 0.83, null)],
        }],
      },
    })
    renderSeparate()
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    expect(await screen.findByText(/No feasible staffing plan/)).toBeInTheDocument()
    const dashes = screen.getAllByText('—')
    expect(dashes.length).toBeGreaterThan(0)
    expect(screen.queryByText('0 cashiers')).not.toBeInTheDocument()
  })

  it('saves a verified snapshot when the schedule is complete', async () => {
    const user = userEvent.setup()
    optimizeSeparateMock.mockResolvedValue(completeSchedule)
    createScenarioMock.mockResolvedValue({ scenario: { id: 9 } })
    renderSeparate()
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('Estimated Optimal Plan')
    const nameInput = screen.getByLabelText('Scenario name') as HTMLInputElement
    expect(nameInput.value).toBe('Optimal @ 70%')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(createScenarioMock).toHaveBeenCalledTimes(1)
    const payload = createScenarioMock.mock.calls[0][0]
    expect(payload.settings.calculation.schema_version).toBe(2)
    expect(payload.settings.calculation.engine_version).toBe('novaq-2026-09-separate-des-v2')
    expect(payload.results.schedule.overall).toBe('COMPLETE')
  })

  it('requests and records full coverage: min_active_lanes equals the configured queue count', async () => {
    const user = userEvent.setup()
    optimizeSeparateMock.mockResolvedValue(completeSchedule)
    createScenarioMock.mockResolvedValue({ scenario: { id: 9 } })
    renderSeparate()
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('Estimated Optimal Plan')
    expect(optimizeSeparateMock).toHaveBeenCalledWith(
      7, 1, expect.objectContaining({ min_active_lanes: 2 }),
    )
    await user.click(screen.getByRole('button', { name: 'Save' }))
    const payload = createScenarioMock.mock.calls[0][0]
    expect(payload.settings.min_active_lanes).toBe(2)
    expect(payload.settings.calculation.options.min_active_lanes).toBe(2)
  })
})

describe('break schedule optimizer', () => {
  function renderAt(structure: 'shared_queue' | 'separate_queues') {
    getAnalysisMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: structure, queue_ids: structure === 'separate_queues' ? ['c1', 'c2'] : [] } },
    })
    return renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/optimize" element={<OptimizePage />} />
      </Routes>,
      { route: '/analyses/7/optimize' },
    )
  }

  const summary = (wait: number, queue: number, served: number) => ({
    mean_wait_minutes: wait, max_queue: queue, admitted: served, served, customer_conservation: true,
  })

  const result = {
    status: 'improved',
    target_rho: 0.85,
    max_shift_minutes: 120,
    all_below_target: true,
    current_breaks: [
      { queue_id: 'c1', label: 'Break 1', scheduled_start_time: '10:00:00', duration_minutes: 30 },
      { queue_id: 'c2', label: 'Break 1', scheduled_start_time: '10:00:00', duration_minutes: 30 },
    ],
    proposed_breaks: [
      { queue_id: 'c1', label: 'Break 1', scheduled_start_time: '10:00:00', duration_minutes: 30, current_start_time: '10:00:00', shift_minutes: 0 },
      { queue_id: 'c2', label: 'Break 1', scheduled_start_time: '11:00:00', duration_minutes: 30, current_start_time: '10:00:00', shift_minutes: 60 },
    ],
    moves: [{ queue_id: 'c2', label: 'Break 1', from: '10:00', to: '11:00', duration_minutes: 30 }],
    slots: [
      { start: '09:45', end: '10:00', lambda: 4, mu: 5, working_before: 2, working_after: 2, rho_before: 0.4, rho_after: 0.4 },
      { start: '10:00', end: '10:15', lambda: 4, mu: 5, working_before: 0, working_after: 1, rho_before: null, rho_after: 0.8 },
      { start: '11:00', end: '11:15', lambda: 2, mu: 5, working_before: 2, working_after: 1, rho_before: 0.2, rho_after: 0.4 },
    ],
    peak_rho: { before: null, after: 0.8 },
    slots_above_target: { before: 2, after: 0 },
    staffing_gaps: [{ start: '12:00', end: '12:15', on_shift: 2, rho_no_breaks: 0.9 }],
    des: {
      seeds: [42, 43],
      current: { summary: summary(3.25, 4, 50), replications: [], periods: [] },
      proposed: { summary: summary(1.5, 2, 50), replications: [], periods: [] },
      comparison: { mean_wait_change_minutes: -1.75, proposed_better_runs: 2, runs: 2 },
    },
    notes: [],
    setup_hash: 'hash-1',
    dataset_id: 1,
  }

  it('hides the break optimizer for shared queues and shows the note', async () => {
    renderAt('shared_queue')
    expect(await screen.findByText('Break optimization is available for separate queues.')).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Break schedule' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Suggest break times' })).not.toBeInTheDocument()
  })

  it('runs the break optimizer and shows breaks, changed slots, gaps, and the DES comparison', async () => {
    const user = userEvent.setup()
    optimizeSeparateBreaksMock.mockResolvedValue(result)
    renderAt('separate_queues')
    expect(await screen.findByRole('heading', { name: 'Break schedule' })).toBeInTheDocument()
    expect(screen.queryByText('Break optimization is available for separate queues.')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Suggest break times' }))
    await waitFor(() => expect(optimizeSeparateBreaksMock).toHaveBeenCalledWith(
      7, expect.objectContaining({ target_rho: 0.85, max_shift_minutes: 120 }),
    ))
    expect(await screen.findByText('The proposed break times lower the busiest point of the day.')).toBeInTheDocument()
    expect(screen.getByText('Peak utilization: no cashier working → 0.80')).toBeInTheDocument()
    const breaks = screen.getByRole('table', { name: 'Current and proposed break times' })
    expect(within(breaks).getAllByRole('row')).toHaveLength(3)
    expect(within(breaks).getByRole('row', { name: /c2 Break 1 10:00 11:00 30 Yes/ })).toBeInTheDocument()
    const slots = screen.getByRole('table', { name: 'Utilization in changed 15-minute slots' })
    expect(within(slots).getAllByRole('row')).toHaveLength(3)
    expect(within(slots).queryByText('09:45–10:00')).not.toBeInTheDocument()
    expect(screen.getByText('12:00–12:15: 2 cashiers on shift, ρ 0.90 with no breaks')).toBeInTheDocument()
    const des = screen.getByRole('table', { name: 'Simulated day: current vs proposed breaks' })
    expect(within(des).getByRole('row', { name: /Average wait \(min\) 3.25 1.50/ })).toBeInTheDocument()
    expect(screen.getByText('Proposed breaks had the shorter average wait in 2 of 2 simulated days.')).toBeInTheDocument()
    expect(screen.getByText(/simulation with simulation, never with recorded waits/)).toBeInTheDocument()
  })

  const withChange = (paired_wait_change: Record<string, unknown>) => ({
    ...result,
    des: { ...result.des, comparison: { ...result.des.comparison, paired_wait_change } },
  })

  it('words the wait result from the paired 95% range and keeps the win count secondary', async () => {
    const user = userEvent.setup()
    optimizeSeparateBreaksMock.mockResolvedValue(withChange({
      mean: -1.75, sd: 0.3, se: 0.2, ci_lower: -2.5, ci_upper: -1.0, n: 2, verdict: 'shorter',
    }))
    renderAt('separate_queues')
    await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
    expect(await screen.findByText('Shorter waits with the proposed breaks')).toBeInTheDocument()
    expect(screen.getByText('Wait change -1.75 min (95% range -2.50 to -1.00)')).toBeInTheDocument()
    const better = screen.getByText('Proposed breaks had the shorter average wait in 2 of 2 simulated days.')
    expect(better).toHaveClass('form-hint')
    expect(screen.getByText('The proposed break times lower the busiest point of the day.')).toBeInTheDocument()
  })

  it('says there is no clear difference when the range is missing or crosses zero', async () => {
    const user = userEvent.setup()
    optimizeSeparateBreaksMock.mockResolvedValue(withChange({
      mean: -2.0, sd: null, se: null, ci_lower: null, ci_upper: null, n: 1, verdict: 'no_clear_difference',
    }))
    renderAt('separate_queues')
    await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
    expect(await screen.findByText('No clear difference in waits')).toBeInTheDocument()
    expect(screen.getByText('Wait change -2.00 min (no 95% range from a single simulated day)')).toBeInTheDocument()
    expect(screen.queryByText('Shorter waits with the proposed breaks')).not.toBeInTheDocument()
  })

  const applyButton = { name: 'Apply to Setup' }

  it('hides Apply to Setup when the proposal has no moves', async () => {
    const user = userEvent.setup()
    optimizeSeparateBreaksMock.mockResolvedValue({ ...result, status: 'no_improvement', moves: [] })
    renderAt('separate_queues')
    await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
    expect(await screen.findByText('Peak utilization: no cashier working → 0.80')).toBeInTheDocument()
    expect(screen.queryByRole('button', applyButton)).not.toBeInTheDocument()
  })

  it('confirms with the list of moves, applies, and invalidates analysis and evidence', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    optimizeSeparateBreaksMock.mockResolvedValue(result)
    applySeparateBreaksMock.mockResolvedValue({ analysis: { id: 7 }, moves_applied: 1 })
    const { queryClient } = renderAt('separate_queues')
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
    await user.click(await screen.findByRole('button', applyButton))
    const message = confirm.mock.calls[0][0] as string
    expect(message).toContain('c2 · Break 1: 10:00 → 11:00')
    expect(message).not.toContain('c1 ·')
    expect(message).toContain('This replaces the break times in Setup. Earlier Current, Simulation and Decision results will need to be rerun.')
    await waitFor(() => expect(applySeparateBreaksMock).toHaveBeenCalledWith(
      7, { target_rho: 0.85, max_shift_minutes: 120, setup_hash: 'hash-1', dataset_id: 1 },
    ))
    expect(await screen.findByText('Setup updated with the proposed breaks. Rerun the workflow from Current.')).toBeInTheDocument()
    for (const key of [['analysis', 7], ['workflow', 7], ['current', 7], ['separate-comparison', 7]]) {
      expect(invalidate).toHaveBeenCalledWith({ queryKey: key })
    }
    expect(screen.queryByRole('button', applyButton)).not.toBeInTheDocument()
    confirm.mockRestore()
  })

  it('disables Apply with a note when the proposal is not on the latest dataset', async () => {
    const user = userEvent.setup()
    listDatasetsMock.mockResolvedValue({ datasets: [{ ...dataset, id: 2, name: 'newer' }, dataset] })
    optimizeSeparateBreaksMock.mockResolvedValue(result)
    renderAt('separate_queues')
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Suggest break times' }))
    await waitFor(() => expect(optimizeSeparateBreaksMock).toHaveBeenCalledWith(
      7, expect.objectContaining({ dataset_id: 1 }),
    ))
    expect(await screen.findByRole('button', applyButton)).toBeDisabled()
    expect(screen.getByText('Apply is available for proposals made on the latest dataset.')).toBeInTheDocument()
  })

  it('does not apply when the confirmation is cancelled', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(false)
    optimizeSeparateBreaksMock.mockResolvedValue(result)
    renderAt('separate_queues')
    await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
    await user.click(await screen.findByRole('button', applyButton))
    expect(applySeparateBreaksMock).not.toHaveBeenCalled()
    confirm.mockRestore()
  })

  it('shows the server message when the Setup changed (409)', async () => {
    const user = userEvent.setup()
    const confirm = vi.spyOn(window, 'confirm').mockReturnValue(true)
    const stale = 'Setup changed since this proposal was made. Run the break optimizer again.'
    optimizeSeparateBreaksMock.mockResolvedValue(result)
    applySeparateBreaksMock.mockRejectedValue({ response: { status: 409, data: { detail: stale } } })
    renderAt('separate_queues')
    await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
    await user.click(await screen.findByRole('button', applyButton))
    expect(await screen.findByRole('alert')).toHaveTextContent(stale)
    expect(screen.queryByText('Setup updated with the proposed breaks. Rerun the workflow from Current.')).not.toBeInTheDocument()
    confirm.mockRestore()
  })
})

describe('staffing plan near-target warning', () => {
  function renderSeparatePlan() {
    getAnalysisMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues', queue_ids: ['lane-a', 'lane-b'] } },
    })
    return renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/optimize" element={<OptimizePage />} />
      </Routes>,
      { route: '/analyses/7/optimize' },
    )
  }

  const schedule = (flag: boolean | null) => ({
    schedule: {
      overall: 'COMPLETE', reason: null, target_utilization: 0.7, evaluation_method: 'DES_REPLICATIONS',
      des: { replications: 5, base_seed: 42, duration_hours: 24, max_events: 10000 },
      periods: [{
        time: '08:00', overall: 'OPTIMAL', reason: null, current_active_lanes: ['lane-a', 'lane-b'],
        optimal_active_lanes: 1, adjustment: -1, evaluation_method: 'DES_REPLICATIONS',
        replication_seeds: [42, 43, 44, 45, 46],
        optimum: {
          active_lane_count: 1, recommendation: 'REDUCE', total_cost: 120.5, candidate_utilization: 0.68,
          estimated_optimal: true, near_target_noise: flag,
          cost_uncertainty: { mean: 120.5, sd: 4.0, se: 1.8, ci_lower: 115.5, ci_upper: 125.5, n: 5 },
        },
        candidates: [],
      }],
    },
  })

  const warning = 'Feasible, but within simulation noise of the target — more replications or a lower target would make this safer.'

  async function runWith(flag: boolean | null) {
    const user = userEvent.setup()
    optimizeSeparateMock.mockResolvedValue(schedule(flag))
    renderSeparatePlan()
    await screen.findByRole('option', { name: 'sample' }, { timeout: 5000 })
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    await user.click(screen.getByRole('button', { name: 'Optimize' }))
    await screen.findByText('Estimated Optimal Plan')
  }

  it('shows the warning beside the plan only when flagged', async () => {
    await runWith(true)
    const row = screen.getByRole('row', { name: /08:00/ })
    expect(within(row).getByText(warning)).toBeInTheDocument()
  })

  it('shows no warning when not flagged', async () => {
    await runWith(false)
    expect(screen.queryByText(warning)).not.toBeInTheDocument()
  })

  it('shows no warning when the flag is null', async () => {
    await runWith(null)
    expect(screen.queryByText(warning)).not.toBeInTheDocument()
  })
})
