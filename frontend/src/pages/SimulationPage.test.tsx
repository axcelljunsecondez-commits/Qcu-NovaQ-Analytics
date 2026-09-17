import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { SimulationPage } from './SimulationPage'

const getWorkflowMock = vi.fn()
const runDesMock = vi.fn()
const runDesCurrentMock = vi.fn()
const runMcMock = vi.fn()
const runMcCurrentMock = vi.fn()
const runValidationMock = vi.fn()
const runValidationCurrentMock = vi.fn()
const getAnalysisMock = vi.fn()

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  runWorkflowDes: (...args: unknown[]) => runDesMock(...args),
  runWorkflowDesCurrent: (...args: unknown[]) => runDesCurrentMock(...args),
  runWorkflowMc: (...args: unknown[]) => runMcMock(...args),
  runWorkflowMcCurrent: (...args: unknown[]) => runMcCurrentMock(...args),
  runWorkflowValidation: (...args: unknown[]) => runValidationMock(...args),
  runWorkflowValidationCurrent: (...args: unknown[]) => runValidationCurrentMock(...args),
}))

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const desRow = {
  time: '08:00-09:00',
  lambda: 30,
  mu: 12,
  c: 4,
  rho_sim: 0.63,
  Lq_sim: 0.7,
  Wq_sim: 0.02,
  max_queue: 7,
  served: 600,
  dropped: 0,
  status: 'Normal',
  error: null,
  simulation_supported: true,
}

const trace = {
  results: [desRow],
  trace: [
    { t: 0.1, type: 'arrival', segment_id: 0, customer_id: 1, server_id: null, queue_len_after: 1 },
    { t: 0.2, type: 'service_start', segment_id: 0, customer_id: 1, server_id: 0, queue_len_after: 0 },
    { t: 0.4, type: 'service_end', segment_id: 0, customer_id: 1, server_id: 0, queue_len_after: 0 },
  ],
  trace_hours: 24,
  total_hours: 24,
  event_count: 3,
  truncated: false,
  abandonment_supported: false,
  segments: [{
    segment_id: 0,
    time: '08:00-09:00',
    lambda: 30,
    mu: 12,
    c: 4,
    selected_model: 'M/M/c',
    simulation_supported: true,
    error: null,
    queue_structure: 'shared',
    initial_queue_depth: 0,
    final_queue_depth: 0,
  }],
}

const mcRow = {
  time: '08:00-09:00',
  lambda: 30,
  mu: 12,
  c: 4,
  rho_mean: 0.63,
  rho_std: 0.04,
  rho_p95: 0.7,
  Lq_mean: 0.8,
  Wq_mean: 0.02,
  failure_rate: 0.01,
  failure_count: 20,
  status: 'PASS',
  error: null,
  ci_Wq_hw: 0.01,
  ci_Lq_hw: 0.02,
  adequate_samples: true,
  failure_rate_ci_lower: 0.007,
  failure_rate_ci_upper: 0.015,
  failure_rate_precision: 'high',
  failure_rate_adequate: true,
}

const validationRow = {
  time: '08:00-09:00',
  lambda: 30,
  mu: 12,
  c: 3,
  c_optimal: 4,
  rho_current: 0.83,
  rho_optimal: 0.625,
  Lq_current: 3.5,
  Lq_optimal: 0.5,
  Wq_current: 0.12,
  Wq_optimal: 0.02,
  sim_rho: 0.63,
  sim_Wq: 0.014,
  sim_max_queue: 7,
  sim_status: 'Normal',
  simulation_supported: true,
  validation_reason: null,
  mc_failure_rate: 0.01,
  mc_adequate: true,
  mc_rho_mean: 0.62,
  mc_rho_p95: 0.75,
  mc_Wq_ci: '1.2 ± 0.1 min',
  mc_failure_rate_precision: 'high',
  mc_failure_rate_adequate: true,
}

function job(kind: string, result: unknown, params: Record<string, unknown> = {}) {
  return {
    id: 10,
    kind,
    status: 'completed',
    params: { analysis_id: 7, scenario_id: 3, ...params },
    result,
    created_at: '2026-09-13T00:00:00Z',
    finished_at: '2026-09-13T00:01:00Z',
  }
}

function workflow(overrides: Record<string, unknown> = {}) {
  return {
    analysis_id: 7,
    selection: job('workflow_selection', { scenario_id: 3 }),
    scenario: { id: 3, name: 'Plan A', dataset_id: 2, provenance: 'verified_snapshot' },
    des: null,
    mc: null,
    validation: null,
    decision: null,
    decision_stale: false,
    ...overrides,
  }
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId/simulate" element={<SimulationPage />} />
    </Routes>,
    { route: '/analyses/7/simulate' },
  )
}

beforeEach(() => {
  getWorkflowMock.mockReset().mockResolvedValue(workflow())
  getAnalysisMock.mockReset().mockResolvedValue({
    analysis: { id: 7, queue_setup: { queue_structure: 'shared_queue' } },
  })
  runDesMock.mockReset().mockResolvedValue({ evidence: job('workflow_des', trace) })
  runMcMock.mockReset().mockResolvedValue({ evidence: job('workflow_mc', { results: [mcRow] }) })
  runValidationCurrentMock.mockReset().mockResolvedValue({
    evidence: job('workflow_validation_current', {
      results: [{ time: '08:00', queue_id: 'cashier-east', mc_failure_rate: 0.01,
                  mc_failure_rate_adequate: true, failure_rate_cap: 0.05, validation_verdict: 'pass' }],
      verdict: { status: 'pass', failed: [], inadequate: [], total: 1 },
    }, { scenario_id: null }),
  })
  runValidationMock.mockReset().mockResolvedValue({
    evidence: job('workflow_validation', { results: [validationRow] }, {
      des_sim_hours: 24,
      mc_trials: 10000,
      mc_failure_threshold: 0.75,
      mc_failure_rate_cap: 0.05,
      seed: null,
    }),
  })
  runDesCurrentMock.mockReset().mockResolvedValue({ evidence: job('workflow_des_current', trace, { scenario_id: null }) })
  runMcCurrentMock.mockReset().mockResolvedValue({ evidence: job('workflow_mc_current', { results: [mcRow] }, { scenario_id: null }) })
})

function separateSetup() {
  getAnalysisMock.mockResolvedValue({
    analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues' } },
  })
}

const separateTrace = {
  ...trace,
  results: [{ ...desRow, c: 1 }],
  trace: [
    { t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_id: 'queue_1', queue_len_after: 1 },
    { t: 0.2, type: 'service_start', segment_id: 's1', customer_id: 1, server_id: 'server:queue_1', queue_id: 'queue_1', queue_len_after: 0 },
    { t: 0.4, type: 'service_end', segment_id: 's1', customer_id: 1, server_id: 'server:queue_1', queue_id: 'queue_1', queue_len_after: 0 },
  ],
  segments: [{
    segment_id: 's1',
    time: '07:00-08:00',
    lambda: 4,
    mu: 4,
    c: 1,
    selected_model: 'Parallel M/G/1',
    simulation_supported: true,
    error: null,
    queue_structure: 'separate',
    initial_queue_depth: 0,
    final_queue_depth: 0,
  }],
}

describe('SimulationPage workflow', () => {
  it('supports Arrow, Home, and End keyboard navigation across simulation tabs', async () => {
    const user = userEvent.setup()
    renderPage()
    const des = await screen.findByRole('tab', { name: 'DES & Live Playback' })
    const mc = screen.getByRole('tab', { name: 'Monte Carlo' })
    const validate = screen.getByRole('tab', { name: 'Validate' })
    des.focus()
    await user.keyboard('{ArrowRight}')
    expect(mc).toHaveFocus()
    expect(mc).toHaveAttribute('aria-selected', 'true')
    await user.keyboard('{End}')
    expect(validate).toHaveFocus()
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', 'simulation-tab-validate')
    await user.keyboard('{Home}')
    expect(des).toHaveFocus()
  })

  it('requires a scenario selected in Compare', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ selection: null, scenario: null }))
    renderPage()
    expect(await screen.findByText(/Select a verified scenario in Compare/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Compare' })).toHaveAttribute('href', '/analyses/7/compare')
  })

  it('shows three simulation categories and no duplicate Live tab', async () => {
    renderPage()
    expect(await screen.findByRole('tab', { name: 'DES & Live Playback' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Monte Carlo' })).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Validate' })).toBeInTheDocument()
    expect(screen.queryByRole('tab', { name: 'Live' })).not.toBeInTheDocument()
  })

  it('uses one persisted DES result for metrics, charts, and playback', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Run DES & Playback' }))
    await waitFor(() => expect(runDesMock).toHaveBeenCalledWith(7, {
      sim_hours: 24,
      queue_overload_threshold: 20,
      max_events: 3000,
      seed: null,
      carryover: true,
    }))
    expect(await screen.findByText('Live queue floor')).toBeInTheDocument()
    expect(screen.getByText('Stable segments')).toBeInTheDocument()
    expect(screen.getAllByText('600')).toHaveLength(2)
    expect(screen.getByRole('region', { name: 'Discrete-event simulation results by interval' })).toBeInTheDocument()
  })

  it('persists Monte Carlo evidence for the selected scenario', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Monte Carlo' }))
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => expect(runMcMock).toHaveBeenCalledWith(7, {
      num_trials: 2000,
      failure_threshold: 0.75,
      failure_rate_cap: 0.05,
      seed: null,
    }))
    expect(await screen.findByText('PASS')).toBeInTheDocument()
  })

  it('validates saved staffing without running optimization in the browser', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Validate' }))
    expect(screen.getByText(/does not run the optimizer again/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Validate plan' }))
    await waitFor(() => expect(runValidationMock).toHaveBeenCalledWith(7, {
      des_sim_hours: 24,
      mc_trials: 10000,
      mc_failure_threshold: 0.75,
      mc_failure_rate_cap: 0.05,
      seed: null,
    }))
    expect(await screen.findByText('Simulation validation passed.')).toBeInTheDocument()
    expect(screen.getByText('Saved validation failure-rate cap: 5%.')).toBeInTheDocument()
  })

  it('keeps a persisted validation verdict bound to its saved cap when next-run settings change', async () => {
    const user = userEvent.setup()
    const failedAtSavedCap = { ...validationRow, mc_failure_rate: 0.1 }
    getWorkflowMock.mockResolvedValue(workflow({
      validation: job('workflow_validation', { results: [failedAtSavedCap] }, {
        des_sim_hours: 24,
        mc_trials: 10000,
        mc_failure_threshold: 0.75,
        mc_failure_rate_cap: 0.05,
        seed: null,
      }),
    }))
    renderPage()

    await user.click(await screen.findByRole('tab', { name: 'Validate' }))
    expect(await screen.findByText('Simulation validation found issues.')).toBeInTheDocument()
    expect(screen.getByText('Saved validation failure-rate cap: 5%.')).toBeInTheDocument()

    await user.click(screen.getByRole('tab', { name: 'Monte Carlo' }))
    const capInput = screen.getByLabelText('Failure rate cap')
    await user.clear(capInput)
    await user.type(capInput, '0.2')
    await user.click(screen.getByRole('tab', { name: 'Validate' }))

    expect(screen.getByText('Simulation validation found issues.')).toBeInTheDocument()
    expect(screen.queryByText('Simulation validation passed.')).not.toBeInTheDocument()
    expect(screen.getByText(/Run settings changed/)).toHaveTextContent('result below still uses the saved run parameters')
  })

  it('blocks invalid failure-rate settings before execution', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('tab', { name: 'Monte Carlo' }))
    const cap = screen.getByLabelText('Failure rate cap')
    await user.clear(cap)
    await user.type(cap, '2')
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Failure rate cap must be between 0 and 1.')
    expect(runMcMock).not.toHaveBeenCalled()
  })
})

describe('SimulationPage Simulate Current mode', () => {
  it('shows Simulate Current for separate queues with no scenario', async () => {
    separateSetup()
    getWorkflowMock.mockResolvedValue(workflow({ selection: null, scenario: null, des_current: null }))
    renderPage()
    expect(await screen.findByRole('heading', { name: 'Simulate Current' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Run Current DES' })).toBeInTheDocument()
    expect(screen.queryByText(/Select a verified scenario in Compare/)).not.toBeInTheDocument()
  })

  it('keeps the scenario-first stop for pooled analyses with no scenario', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ selection: null, scenario: null }))
    renderPage()
    expect(await screen.findByText(/Select a verified scenario in Compare/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run Current DES' })).not.toBeInTheDocument()
  })

  it('runs Current DES, shows CURRENT provenance, and never claims optimized', async () => {
    const user = userEvent.setup()
    separateSetup()
    getWorkflowMock.mockResolvedValue(workflow({ selection: null, scenario: null, des_current: null }))
    runDesCurrentMock.mockResolvedValue({ evidence: job('workflow_des_current', { ...separateTrace, provenance: 'CURRENT' }, { scenario_id: null }) })
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Run Current DES' }))
    await waitFor(() => expect(runDesCurrentMock).toHaveBeenCalledWith(7, {
      sim_hours: 24,
      queue_overload_threshold: 20,
      max_events: 3000,
      seed: null,
      carryover: true,
    }))
    expect(runDesMock).not.toHaveBeenCalled()
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()
    expect(screen.queryByText(/Verified scenario|Recommended|Plan A/)).not.toBeInTheDocument()
  })

  it('restores persisted des_current on load without rerunning', async () => {
    separateSetup()
    getWorkflowMock.mockResolvedValue(workflow({
      selection: null,
      scenario: null,
      des_current: job('workflow_des_current', { ...separateTrace, provenance: 'CURRENT' }, { scenario_id: null }),
    }))
    renderPage()
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()
    expect(runDesCurrentMock).not.toHaveBeenCalled()
  })

  it('routes a separate Current-DES trace to the separate playback layout', async () => {
    separateSetup()
    getWorkflowMock.mockResolvedValue(workflow({
      selection: null,
      scenario: null,
      des_current: job('workflow_des_current', { ...separateTrace, provenance: 'CURRENT' }, { scenario_id: null }),
    }))
    renderPage()
    expect(await screen.findByTestId('lane-queue_1')).toBeInTheDocument()
  })

  it('renders opaque queue IDs as separate playback lanes', async () => {
    separateSetup()
    const eastTrace = {
      ...separateTrace,
      trace: [
        { t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_id: 'cashier-east', queue_len_after: 1 },
        { t: 0.2, type: 'service_start', segment_id: 's1', customer_id: 1, server_id: 'server:cashier-east', queue_id: 'cashier-east', queue_len_after: 0 },
        { t: 0.4, type: 'service_end', segment_id: 's1', customer_id: 1, server_id: 'server:cashier-east', queue_id: 'cashier-east', queue_len_after: 0 },
      ],
    }
    getWorkflowMock.mockResolvedValue(workflow({
      selection: null,
      scenario: null,
      des_current: job('workflow_des_current', { ...eastTrace, provenance: 'CURRENT' }, { scenario_id: null }),
    }))
    renderPage()
    expect(await screen.findByTestId('lane-cashier-east')).toBeInTheDocument()
    expect(screen.queryByTestId('lane-queue_1')).not.toBeInTheDocument()
  })

  it('gates Validate on Current-MC evidence while Monte Carlo runs per queue', async () => {
    const user = userEvent.setup()
    separateSetup()
    getWorkflowMock.mockResolvedValue(workflow({ selection: null, scenario: null, des_current: null }))
    renderPage()
    expect(await screen.findByRole('button', { name: 'Run Current DES' })).toBeInTheDocument()
    expect(screen.queryByRole('tab')).not.toBeInTheDocument()
    expect(screen.queryByText(/Monte Carlo requires a verified scenario/)).not.toBeInTheDocument()
    expect(screen.getByText(/needs Current Monte Carlo evidence first/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Validate plan' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => expect(runMcCurrentMock).toHaveBeenCalledWith(7, expect.objectContaining({
      num_trials: 2000,
    })))
    expect(runMcMock).not.toHaveBeenCalled()
  })

  it('restores persisted Current-MC with per-queue identity without rerunning', async () => {
    separateSetup()
    const queuedRow = { ...mcRow, queue_id: 'cashier-east' }
    getWorkflowMock.mockResolvedValue(workflow({
      selection: null,
      scenario: null,
      des_current: null,
      mc_current: job('workflow_mc_current', { results: [queuedRow] }, { scenario_id: null }),
    }))
    renderPage()
    expect(await screen.findByText('cashier-east')).toBeInTheDocument()
    expect(runMcCurrentMock).not.toHaveBeenCalled()
  })

  it('runs Current validation from persisted MC and shows the per-queue verdict', async () => {
    const user = userEvent.setup()
    separateSetup()
    const queuedRow = { ...mcRow, queue_id: 'cashier-east' }
    getWorkflowMock.mockResolvedValue(workflow({
      selection: null,
      scenario: null,
      des_current: null,
      mc_current: job('workflow_mc_current', { results: [queuedRow] }, { scenario_id: null }),
    }))
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Validate plan' }))
    await waitFor(() => expect(runValidationCurrentMock).toHaveBeenCalledWith(7))
    expect(runValidationMock).not.toHaveBeenCalled()
  })

  it('restores a persisted Current validation verdict without rerunning', async () => {
    separateSetup()
    getWorkflowMock.mockResolvedValue(workflow({
      selection: null,
      scenario: null,
      des_current: null,
      mc_current: job('workflow_mc_current', { results: [{ ...mcRow, queue_id: 'cashier-east' }] }, { scenario_id: null }),
      validation_current: job('workflow_validation_current', {
        results: [{ time: '08:00', queue_id: 'cashier-east', mc_failure_rate: 0.01,
                    mc_failure_rate_adequate: true, failure_rate_cap: 0.05, validation_verdict: 'pass' }],
        verdict: { status: 'pass', failed: [], inadequate: [], total: 1 },
      }, { scenario_id: null }),
    }))
    renderPage()
    expect(await screen.findByText('Simulation validation passed.')).toBeInTheDocument()
    expect(screen.getAllByText('cashier-east').length).toBeGreaterThanOrEqual(2)
    expect(runValidationCurrentMock).not.toHaveBeenCalled()
  })
})
