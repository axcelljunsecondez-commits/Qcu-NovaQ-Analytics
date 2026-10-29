import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes, useLocation } from 'react-router-dom'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useQuery } from '@tanstack/react-query'
import { renderWithProviders } from '../test/test-utils'
import { QueueSimulationPage } from './QueueSimulationPage'
import { RunBar } from '../components/queueSimulation/RunBar'
import { KeyResultsView } from '../components/queueSimulation/KeyResultsView'
import { ReplayView } from '../components/queueSimulation/ReplayView'
import { buildContext, defaultRun } from '../components/queueSimulation/simulationContext'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'

// Queue simulation (spec 2026-10-09 §7.8, D28/D30; plan phase U7a), ported from the former
// SimulationPage tests: the same requests, bindings and refusals, on three pages.

const getWorkflowMock = vi.fn()
const runDesMock = vi.fn()
const runDesCurrentMock = vi.fn()
const runMcMock = vi.fn()
const runMcCurrentMock = vi.fn()
const runValidationMock = vi.fn()
const runValidationCurrentMock = vi.fn()
const createDecisionMock = vi.fn()
const runSelectedDesMock = vi.fn()
const runSelectedMcMock = vi.fn()
const runSelectedValidationMock = vi.fn()
const runSelectedDecisionMock = vi.fn()
const optimizeSpy = vi.fn()
const getAnalysisMock = vi.fn()
const patchAnalysisMock = vi.fn()
const getAnalysisCurrentMock = vi.fn()
const getClosingPolicyMock = vi.fn()
const putClosingPolicyMock = vi.fn()
const getCompatibilityMock = vi.fn()
const createContinuousRunMock = vi.fn()
const listContinuousRunsMock = vi.fn()
const getContinuousRunMock = vi.fn()
const getContinuousPlaybackMock = vi.fn()

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  runWorkflowDes: (...args: unknown[]) => runDesMock(...args),
  runWorkflowDesCurrent: (...args: unknown[]) => runDesCurrentMock(...args),
  runWorkflowMc: (...args: unknown[]) => runMcMock(...args),
  runWorkflowMcCurrent: (...args: unknown[]) => runMcCurrentMock(...args),
  runWorkflowValidation: (...args: unknown[]) => runValidationMock(...args),
  runWorkflowValidationCurrent: (...args: unknown[]) => runValidationCurrentMock(...args),
  createWorkflowDecision: (...args: unknown[]) => createDecisionMock(...args),
  runSelectedDes: (...args: unknown[]) => runSelectedDesMock(...args),
  runSelectedMc: (...args: unknown[]) => runSelectedMcMock(...args),
  runSelectedValidation: (...args: unknown[]) => runSelectedValidationMock(...args),
  runSelectedDecision: (...args: unknown[]) => runSelectedDecisionMock(...args),
}))
vi.mock('../api/continuous', () => ({
  getClosingPolicy: (...args: unknown[]) => getClosingPolicyMock(...args),
  putClosingPolicy: (...args: unknown[]) => putClosingPolicyMock(...args),
  getContinuousCompatibility: (...args: unknown[]) => getCompatibilityMock(...args),
  createContinuousRun: (...args: unknown[]) => createContinuousRunMock(...args),
  listContinuousRuns: (...args: unknown[]) => listContinuousRunsMock(...args),
  getContinuousRun: (...args: unknown[]) => getContinuousRunMock(...args),
  getContinuousPlayback: (...args: unknown[]) => getContinuousPlaybackMock(...args),
}))
vi.mock('../api/optimization', () => ({
  optimize: (...args: unknown[]) => optimizeSpy(...args),
  optimizeBatch: (...args: unknown[]) => optimizeSpy(...args),
  optimizeSeparate: (...args: unknown[]) => optimizeSpy(...args),
}))
vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: (...args: unknown[]) => patchAnalysisMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getAnalysisCurrentMock(...args),
  listAnalyses: vi.fn(async () => ({ analyses: [{ id: 7, name: 'Checkout', archived_at: null }] })),
}))
vi.mock('../components/simulation/NamedSharedQueueSimulation', () => ({
  NamedSharedQueueSimulation: ({ modeSwitch }: { modeSwitch: unknown }) => <div data-testid="named-view">{modeSwitch as never}</div>,
}))
vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' } })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const desRow = {
  time: '08:00-09:00', lambda: 30, mu: 12, c: 4, rho_sim: 0.63, Lq_sim: 0.7, Wq_sim: 0.02, max_queue: 7, served: 600, dropped: 0,
  status: 'Normal', error: null, simulation_supported: true,
}
const perPeriodSummary = {
  basis: 'per_period', average_wait_hours: 0.02, longest_line: 7, arrivals: null, served: null, in_system_at_close: null,
  periods: [{ time: '08:00-09:00', average_wait_hours: 0.02, longest_line: 7, arrivals: null, served: null }],
}
const trace = {
  results: [desRow],
  trace: [
    { t: 0.1, type: 'arrival', segment_id: 0, customer_id: 1, server_id: null, queue_len_after: 1 },
    { t: 0.2, type: 'service_start', segment_id: 0, customer_id: 1, server_id: 0, queue_len_after: 0 },
    { t: 0.4, type: 'service_end', segment_id: 0, customer_id: 1, server_id: 0, queue_len_after: 0 },
  ],
  trace_hours: 24, total_hours: 24, event_count: 3, truncated: false, abandonment_supported: false,
  segments: [{ segment_id: 0, time: '08:00-09:00', lambda: 30, mu: 12, c: 4, selected_model: 'M/M/c', simulation_supported: true, error: null,
    queue_structure: 'shared', initial_queue_depth: 0, final_queue_depth: 0 }],
  summary: perPeriodSummary,
}
const mcRow = {
  time: '08:00-09:00', lambda: 30, mu: 12, c: 4, rho_mean: 0.63, rho_std: 0.04, rho_p95: 0.7, Lq_mean: 0.8, Wq_mean: 0.02, failure_rate: 0.01,
  failure_count: 20, status: 'PASS', error: null, ci_Wq_hw: 0.01, ci_Lq_hw: 0.02, adequate_samples: true, failure_rate_ci_lower: 0.007,
  failure_rate_ci_upper: 0.015, failure_rate_precision: 'high', failure_rate_adequate: true,
}
const validationRow = {
  time: '08:00-09:00', lambda: 30, mu: 12, c: 3, c_optimal: 4, rho_current: 0.83, rho_optimal: 0.625, Lq_current: 3.5, Lq_optimal: 0.5,
  Wq_current: 0.12, Wq_optimal: 0.02, sim_rho: 0.63, sim_Wq: 0.014, sim_max_queue: 7, sim_status: 'Normal', simulation_supported: true,
  validation_reason: null, mc_failure_rate: 0.01, mc_adequate: true, mc_rho_mean: 0.62, mc_rho_p95: 0.75, mc_Wq_ci: '1.2 ± 0.1 min',
  mc_failure_rate_precision: 'high', mc_failure_rate_adequate: true,
}

function job(kind: string, result: unknown, params: Record<string, unknown> = {}) {
  return { id: 10, kind, status: 'completed', params: { analysis_id: 7, scenario_id: 3, ...params }, result,
    created_at: '2026-09-13T00:00:00Z', finished_at: '2026-09-13T00:01:00Z' }
}

function workflow(overrides: Record<string, unknown> = {}) {
  return {
    analysis_id: 7, selection: job('workflow_selection', { scenario_id: 3 }),
    scenario: { id: 3, name: 'Plan A', dataset_id: 2, provenance: 'verified_snapshot' },
    des: null, mc: null, validation: null, des_current: null, mc_current: null, validation_current: null,
    decision: null, decision_stale: false, ...overrides,
  }
}

function setupOf(structure: 'shared_queue' | 'separate_queues', extra: Record<string, unknown> = {}) {
  return { analysis: { id: 7, name: 'Checkout', queue_setup: { queue_structure: structure, segments: [], breaks: [], ...extra } } }
}

const compatiblePlan = {
  compatible: true, reasons: [], expected_customers_per_day: 13, horizon: { start_minute: 480, end_minute: 600 },
  dataset_id: 9, scenario_id: null, scenario_name: null,
}
function compatibility(overrides: Record<string, unknown> = {}, closing: string | null = 'DRAIN') {
  return {
    closing_policy: closing,
    plans: { current: compatiblePlan, suggested: { ...compatiblePlan, scenario_id: 3, scenario_name: 'Plan A' } },
    default_replications: 5, default_seed: 42,
    limits: { max_replications: 9, max_expected_customers_per_run: 2900, result_max_bytes: 786432, status: 'provisional_not_production_approved' },
    preview: true, model_scope: 'Preview', verdict: null, verdict_reason: 'No rule.', ...overrides,
  }
}
const metric = (mean: number | null, min: number | null, max: number | null) => ({ mean, min, max, n: 5, n_undefined: 0, ci_lower: null, ci_upper: null })
function continuousRun(id: number, plan: 'current' | 'suggested', { waitHours = 0.07, served = 12, extra = {} as Record<string, unknown> } = {}) {
  return {
    evidence: {
      id, kind: 'shared_continuous_preview', created_at: '2026-10-12T00:00:00Z',
      params: { analysis_id: 7, plan, scenario_id: plan === 'suggested' ? 3 : null, dataset_id: 9, replications: 5, seed: 42, closing_policy: 'DRAIN' },
      result: {
        replications: [],
        summary: {
          replications: 5,
          customers: { arrivals: 65, served: 65, unserved: 0, conserved_in_every_replication: true,
            per_replication: { arrivals: metric(13, 10, 16), served: metric(served, 10, 16), unserved: metric(0, 0, 0) } },
          waiting_time: { mean_of_replication_means_hours: metric(waitHours, 0.05, 0.1), customer_weighted_mean_hours: { value: waitHours } },
          metrics: { max_queue_in_horizon: metric(3.4, 2, 5), utilization_in_horizon: metric(0.62, 0.5, 0.7) },
        },
        provenance: { replications: 5, seed: 42, closing_policy: 'DRAIN', engine_version: 'novaq-shared-continuous-des-v2',
          inputs: { horizon: { start_minute: 480, end_minute: 600 }, demand_periods: [], staffing_segments: [] } },
      },
    },
    setup_matches_current: true, dataset_is_current: true, plan_is_selected: plan === 'suggested' ? true : null, ...extra,
  }
}
const dayPlayback = {
  replication_index: 0,
  playback: {
    events: [
      { seq: 0, t: 0, type: 'server_open', queue_len_after: 0, servers_idle_after: 1, servers_busy_after: 0, servers_draining_after: 0 },
      { seq: 1, t: 0.25, type: 'arrival', queue_len_after: 1, servers_idle_after: 1, servers_busy_after: 0, servers_draining_after: 0 },
      { seq: 2, t: 0.25, type: 'service_start', queue_len_after: 0, servers_idle_after: 0, servers_busy_after: 1, servers_draining_after: 0 },
      { seq: 3, t: 0.5, type: 'arrival', queue_len_after: 1, servers_idle_after: 0, servers_busy_after: 1, servers_draining_after: 0 },
      { seq: 4, t: 0.6, type: 'service_end', queue_len_after: 1, servers_idle_after: 1, servers_busy_after: 0, servers_draining_after: 0 },
      { seq: 5, t: 0.6, type: 'service_start', queue_len_after: 0, servers_idle_after: 0, servers_busy_after: 1, servers_draining_after: 0 },
      { seq: 6, t: 1.1, type: 'service_end', queue_len_after: 0, servers_idle_after: 1, servers_busy_after: 0, servers_draining_after: 0 },
      { seq: 7, t: 2, type: 'closing', queue_len_after: 0, servers_idle_after: 0, servers_busy_after: 0, servers_draining_after: 0 },
    ],
    closing: { closing_hours: 2, overrun_hours: 0 },
    customers: [
      { customer_id: 1, arrival_hours: 0.25, service_start_hours: 0.25, service_end_hours: 0.6, server_id: 1, status: 'departed' },
      { customer_id: 2, arrival_hours: 0.5, service_start_hours: 0.6, service_end_hours: 1.1, server_id: 1, status: 'departed' },
    ],
    servers: [{ server_id: 1, intervals: [
      { state: 'IDLE', customer_id: null, start: 0, end: 0.25 },
      { state: 'BUSY', customer_id: 1, start: 0.25, end: 0.6 },
      { state: 'BUSY', customer_id: 2, start: 0.6, end: 1.1 },
      { state: 'IDLE', customer_id: null, start: 1.1, end: 2 },
    ] }],
  },
  by_period: [
    { period_id: '08:00-09:00', start_hours: 0, end_hours: 1, arrivals: 2, served: 2, unserved: 0, mean_wait_hours: 0.05 },
    { period_id: '09:00-10:00', start_hours: 1, end_hours: 2, arrivals: 0, served: 0, unserved: 0, mean_wait_hours: null },
  ],
  preview: true,
}

/** Direct legacy-renderer contract tests; the shared product screen no longer mounts this panel. */
async function olderRun() {
  return within(await screen.findByRole('region', { name: 'Period-by-period run (older method)' }))
}

function LegacyComponents({ replay = false }: { replay?: boolean }) {
  const analysis = useQuery({ queryKey: ['analysis', 7], queryFn: () => getAnalysisMock(7) })
  const saved = useQuery({ queryKey: ['workflow', 7], queryFn: () => getWorkflowMock(7) })
  if (!analysis.data || !saved.data) return null
  const context = buildContext(7, analysis.data.analysis, saved.data)
  const run = defaultRun(context)
  return (
    <section aria-label="Period-by-period run (older method)">
      <RunBar context={context} run={run} />
      {replay ? <ReplayView context={context} run={run} /> : <KeyResultsView context={context} run={run} />}
    </section>
  )
}

function renderLegacyComponents(path = '/simulation/results?analysis=7') {
  return renderWithProviders(<LegacyComponents replay={path.includes('/replay')} />, { route: path })
}

function Where() {
  const location = useLocation()
  return <output data-testid="where">{location.pathname}{location.search}</output>
}

function renderPage(path = '/simulation/results?analysis=7', lang: 'en' | 'tl' = 'en') {
  return renderWithProviders(
    <>
      <Routes>
        <Route path="/simulation/results" element={<QueueSimulationPage page="results" />} />
        <Route path="/simulation/replay" element={<QueueSimulationPage page="replay" />} />
        <Route path="/simulation/checks" element={<QueueSimulationPage page="checks" />} />
      </Routes>
      <Where />
    </>,
    { route: path, lang },
  )
}

function currentDatasetResponse(datasetId: number) {
  return { dataset: { id: datasetId, analysis_id: 7, name: 'Checkout week' }, rows: [], kpis: {}, explanations: [] }
}

beforeEach(() => {
  getWorkflowMock.mockReset().mockResolvedValue(workflow())
  getAnalysisMock.mockReset().mockResolvedValue(setupOf('shared_queue'))
  patchAnalysisMock.mockReset()
  getAnalysisCurrentMock.mockReset().mockResolvedValue(currentDatasetResponse(9))
  runDesMock.mockReset().mockResolvedValue({ evidence: job('workflow_des', trace) })
  runMcMock.mockReset().mockResolvedValue({ evidence: job('workflow_mc', { results: [mcRow] }) })
  runValidationMock.mockReset().mockResolvedValue({
    evidence: job('workflow_validation', { results: [validationRow] }, { des_sim_hours: 24, mc_trials: 10000, mc_failure_threshold: 0.75, mc_failure_rate_cap: 0.05, seed: null }),
  })
  createDecisionMock.mockReset().mockResolvedValue({ decision: { status: 'conditional', headline: 'Consider Plan A conditionally.', recommendation: '', rationale: [],
    missing_evidence: [], scenario_id: 3, scenario_name: 'Plan A', dataset_id: 2, evidence_ids: {}, provenance_warning: '' }, persisted: true })
  runDesCurrentMock.mockReset().mockResolvedValue({ evidence: job('workflow_des_current', trace, { scenario_id: null }) })
  runMcCurrentMock.mockReset().mockResolvedValue({ evidence: job('workflow_mc_current', { results: [mcRow] }, { scenario_id: null }) })
  runValidationCurrentMock.mockReset().mockResolvedValue({
    evidence: job('workflow_validation_current', {
      results: [{ time: '08:00', queue_id: 'cashier-east', mc_failure_rate: 0.01, mc_failure_rate_adequate: true, failure_rate_cap: 0.05, validation_verdict: 'pass' }],
      verdict: { status: 'pass', failed: [], inadequate: [], total: 1 },
    }, { scenario_id: null }),
  })
  for (const mock of [runSelectedDesMock, runSelectedMcMock, runSelectedValidationMock, runSelectedDecisionMock, optimizeSpy]) mock.mockReset()
  getClosingPolicyMock.mockReset().mockResolvedValue({ closing_policy: 'DRAIN', choices: [] })
  putClosingPolicyMock.mockReset().mockResolvedValue({ closing_policy: 'DRAIN' })
  getCompatibilityMock.mockReset().mockResolvedValue(compatibility())
  createContinuousRunMock.mockReset()
  listContinuousRunsMock.mockReset().mockResolvedValue({ runs: [] })
  getContinuousRunMock.mockReset()
  getContinuousPlaybackMock.mockReset().mockResolvedValue(dayPlayback)
})

describe('Queue simulation shell (D28)', () => {
  it('opens Key results with the run switch and page links that keep the address', async () => {
    const user = userEvent.setup()
    renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: "Queue Simulation" })).toBeInTheDocument()
    const pages = await screen.findByRole('navigation', { name: 'Queue simulation pages' })
    expect(within(pages).getAllByRole('link').map((link) => link.textContent)).toEqual(["Key Results", 'Replay', 'Checks and Decisions'])
    expect(within(pages).getByRole('link', { name: "Key Results" })).toHaveAttribute('aria-current', 'page')
    expect(screen.getByRole('button', { name: 'Suggested plan' })).toHaveAttribute('aria-pressed', 'true')
    await user.click(screen.getByRole('button', { name: 'Current' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/simulation/results?analysis=7&plan=current')
    expect(within(pages).getByRole('link', { name: 'Replay' })).toHaveAttribute('href', '/simulation/replay?analysis=7&plan=current')
  })

  it('renders the named view for ?mode=named without a plan or workflow request', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
    renderPage('/simulation/results?analysis=7&mode=named')
    expect(await screen.findByTestId('named-view')).toBeInTheDocument()
    expect(getWorkflowMock).not.toHaveBeenCalled()
  })

  it('switches between the legacy and named modes through the address', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('radio', { name: /named/i }))
    expect(screen.getByTestId('where')).toHaveTextContent('mode=named')
    expect(await screen.findByTestId('named-view')).toBeInTheDocument()
  })
})

describe('shared full-day-only screen', () => {
  it.each(['results', 'replay', 'checks'])('removes the older shared panel on %s without requesting legacy DES', async (page) => {
    renderPage(`/simulation/${page}?analysis=7`)
    await screen.findByRole('region', { name: 'Full-day run' })
    expect(screen.queryByRole('region', { name: 'Period-by-period run (older method)' })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run period by period' })).not.toBeInTheDocument()
    expect(runDesMock).not.toHaveBeenCalled()
    expect(runDesCurrentMock).not.toHaveBeenCalled()
    if (page === 'checks') expect(screen.getByRole('button', { name: 'Check the plan' })).toBeInTheDocument()
  })

  it('draws the full-day visual from the saved playback across an hourly boundary', async () => {
    listContinuousRunsMock.mockResolvedValue({ runs: [{ id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN',
      setup_matches_current: true, dataset_is_current: true, plan_is_selected: true }] })
    getContinuousRunMock.mockResolvedValue(continuousRun(31, 'suggested'))
    const user = userEvent.setup()
    renderPage('/simulation/replay?analysis=7')
    const floor = await screen.findByRole('region', { name: 'Live queue floor' })
    fireEvent.change(screen.getByLabelText('Go to time'), { target: { value: '09:00' } })
    await user.click(screen.getByRole('button', { name: 'Go' }))
    expect(within(floor).getByTestId('continuous-serving-customer-2')).toBeInTheDocument()
    expect(within(floor).getByTestId('continuous-served-customer-1')).toBeInTheDocument()
    expect(within(floor).queryByTestId('continuous-waiting-customer-2')).not.toBeInTheDocument()
    expect(screen.getByTestId('continuous-clock')).toHaveTextContent('09:00')
  })
})

describe('shared selection/checks and legacy renderer contracts', () => {
  it('asks for a plan from Suggested plans before a plan run', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
    renderPage('/simulation/results?analysis=7&plan=suggested')
    expect(await screen.findByText(/Choose a plan in Suggested plans \(Use this plan\)/)).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Suggested Plans' })).toHaveAttribute('href', '/analyses/7/plans')
    expect(screen.queryByRole('button', { name: 'Run full operation' })).not.toBeInTheDocument()
  })

  it('runs the plan once with the labelled defaults and never optimizes in the browser', async () => {
    const user = userEvent.setup()
    renderLegacyComponents()
    expect(await screen.findByTestId('run-status')).toHaveTextContent('Not run')
    await user.click(screen.getByRole('button', { name: 'Run period by period' }))
    await waitFor(() => expect(runDesMock).toHaveBeenCalledWith(7, { sim_hours: 24, queue_overload_threshold: 20, max_events: 3000, seed: null, carryover: true }))
    expect(screen.getByText('One period at a time', { exact: false })).toBeInTheDocument()
    expect(optimizeSpy).not.toHaveBeenCalled()
  })

  it('shows the capability errors of a run that could not simulate any period', async () => {
    const user = userEvent.setup()
    const unsupported = { ...desRow, simulation_supported: false, status: 'ERROR', error: 'Unsupported simulation model: M/G/c.' }
    runDesMock.mockResolvedValue({ evidence: job('workflow_des', { ...trace, results: [unsupported, { ...unsupported, time: '09:00-10:00' }] }) })
    renderLegacyComponents()
    await user.click(await screen.findByRole('button', { name: 'Run period by period' }))
    const errors = await screen.findByTestId('run-capability-errors')
    expect(errors).toHaveTextContent('This run could not simulate any period, so it was not saved:')
    expect(errors).toHaveTextContent('08:00-09:00: Unsupported simulation model: M/G/c.')
    expect(errors).toHaveTextContent('09:00-10:00: Unsupported simulation model: M/G/c.')
    expect(screen.queryByText('NaN')).not.toBeInTheDocument()
  })

  it('blocks invalid run settings before any request', async () => {
    const user = userEvent.setup()
    renderLegacyComponents()
    const hours = await screen.findByLabelText('Hours per segment')
    await user.clear(hours)
    await user.type(hours, '0')
    await user.click(screen.getByRole('button', { name: 'Run period by period' }))
    expect(screen.getByRole('alert')).toBeInTheDocument()
    expect(runDesMock).not.toHaveBeenCalled()
  })

  it('shows the server totals of both runs and never sums customers of a period-by-period run', async () => {
    getWorkflowMock.mockResolvedValue(workflow({
      des: job('workflow_des', { ...trace, summary: { ...perPeriodSummary, average_wait_hours: 0.05, longest_line: 3 } }),
      des_current: job('workflow_des_current', { ...trace, summary: { ...perPeriodSummary, average_wait_hours: 0.1, longest_line: 9 } }, { scenario_id: null }),
    }))
    renderLegacyComponents()
    const older = await olderRun()
    const wait = await older.findByRole('region', { name: 'Average wait' })
    expect(wait).toHaveTextContent('Current: 6 min')
    expect(wait).toHaveTextContent('Suggested plan: 3 min')
    expect(older.getByRole('region', { name: 'Longest Single Line' })).toHaveTextContent('Current: 9')
    // Spec 2026-10-29 §7.3 (B5): two cards, no arrow; Customer Served sits under More results with an
    // explanation instead of the old "Run the full day" note, without assuming a supported full-day run.
    expect(within(older.getByRole('group', { name: 'Key Results' })).getAllByRole('region')).toHaveLength(2)
    expect(older.getByRole('group', { name: 'Key Results' })).not.toHaveTextContent('→')
    const served = older.getByRole('region', { name: 'Customer Served' })
    expect(served.closest('details')).not.toBeNull()
    expect(served).toHaveTextContent('Current: Unavailable')
    expect(served).not.toHaveTextContent('Run the full day to see total customers.')
    const why = within(served).getAllByRole('button', { name: 'Why this is unavailable' })
    expect(why).toHaveLength(2)
    await userEvent.setup().hover(why[0])
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['charts.key_unavailable_explain'])
    expect(screen.getByRole('tooltip')).not.toHaveTextContent('full-day run above')
    // Both runs simulate one period at a time: no basis explanation, and the same-basis takeaway.
    expect(older.queryByRole('button', { name: 'Why these are not the same basis' })).not.toBeInTheDocument()
    expect(older.getByTestId('key-take')).toHaveTextContent('Simulated average wait: Current 6 min, Suggested plan 3 min.')
    expect(older.queryByTestId('closing-alert')).not.toBeInTheDocument()
  })

  it('asks to run again when a stored run has no saved totals', async () => {
    const { summary: _drop, ...old } = trace
    getWorkflowMock.mockResolvedValue(workflow({ des: job('workflow_des', old) }))
    renderLegacyComponents()
    expect(await (await olderRun()).findByRole('region', { name: 'Average wait' })).toHaveTextContent('Suggested plan: Run again to see this')
  })

  it('replays the legacy run one period at a time', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ des: job('workflow_des', trace) }))
    renderLegacyComponents('/simulation/replay?analysis=7')
    expect(await screen.findByText('This run simulates one period at a time; it is not one continuous day.')).toBeInTheDocument()
    expect(screen.getByText('Shared queue view')).toBeInTheDocument()
  })

  it('checks the plan: Results check, then the Decision', async () => {
    const user = userEvent.setup()
    renderPage('/simulation/checks?analysis=7')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    await waitFor(() => expect(createDecisionMock).toHaveBeenCalledTimes(1))
    expect(runValidationMock).toHaveBeenCalledWith(7, { des_sim_hours: 24, mc_trials: 10000, mc_failure_threshold: 0.75, mc_failure_rate_cap: 0.05, seed: null })
    expect(runValidationMock.mock.invocationCallOrder[0]).toBeLessThan(createDecisionMock.mock.invocationCallOrder[0])
    expect(runMcMock).not.toHaveBeenCalled()
    expect(await screen.findByText(/Consider Plan A conditionally/)).toBeInTheDocument()
    // U10 F5: the plain answer to the spec's question, from the stored status.
    expect(screen.getByRole('heading', { name: 'Should we use this plan?' })).toBeInTheDocument()
    expect(screen.getByTestId('decision-plain')).toHaveTextContent('The plan passed every check, but it costs more than today.')
  })

  it('says which evidence a shared Decision is missing, and how many periods failed', async () => {
    const user = userEvent.setup()
    createDecisionMock.mockResolvedValueOnce({ decision: { status: 'insufficient_evidence', headline: 'Insufficient evidence to make a management recommendation.',
      recommendation: '', rationale: [], missing_evidence: ['completed Setup', 'a complete modeled cost comparison'], scenario_id: 3, scenario_name: 'Plan A',
      dataset_id: 2, evidence_ids: {}, provenance_warning: '' }, persisted: true })
    renderPage('/simulation/checks?analysis=7')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent('Not enough checks yet. Run: completed Setup; a complete modeled cost comparison')
    createDecisionMock.mockResolvedValueOnce({ decision: { status: 'revise', headline: 'Do not adopt Scenario "Plan A" yet.', recommendation: '', rationale: [],
      missing_evidence: [], scenario_id: 3, scenario_name: 'Plan A', dataset_id: 2, evidence_ids: {}, provenance_warning: '',
      facts: { validation_intervals: 4, failed_intervals: 1 } }, persisted: true })
    await user.click(screen.getByRole('button', { name: 'Check the plan' }))
    await waitFor(() => expect(screen.getByTestId('decision-plain')).toHaveTextContent('Change the plan first. It did not hold up in 1 of 4 periods.'))
  })

  it('says the saving cannot be calculated when today cannot keep up in a period', async () => {
    const user = userEvent.setup()
    createDecisionMock.mockResolvedValueOnce({ decision: { status: 'conditional', headline: 'Consider Scenario "Plan A" conditionally.',
      recommendation: 'All 4 validation intervals passed, but the cost change cannot be calculated.', rationale: [], missing_evidence: [],
      scenario_id: 3, scenario_name: 'Plan A', dataset_id: 2, evidence_ids: {}, provenance_warning: '',
      facts: { validation_intervals: 4, failed_intervals: 0, current_modeled_cost: null, modeled_savings: null, today_overloaded_periods: ['segment_3'] } },
    persisted: true })
    renderPage('/simulation/checks?analysis=7')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    await waitFor(() => expect(screen.getByTestId('decision-plain')).toHaveTextContent(
      "The plan passed every check, but its cost saving can't be calculated: today's staff can't keep up in segment_3. Use it only if you accept the cost."))
    expect(screen.getByTestId('decision-plain')).not.toHaveTextContent('costs more than today')
  })

  // Spec 2026-10-29-shared-mc-plan-target-threshold.md §5: shared Many variations counts at the plan's target.
  const sharedPlanAt70 = { scenario: { id: 3, name: 'Plan A', dataset_id: 2, provenance: 'verified_snapshot',
    settings: { calculation: { schema_version: 1, engine_version: 'novaq-2026-09-system-v2', options: { target_utilization: 0.7 } } } } }

  it('starts shared Many variations at the plan target and lets the server record it', async () => {
    const user = userEvent.setup()
    getWorkflowMock.mockResolvedValue(workflow(sharedPlanAt70))
    renderPage('/simulation/checks?analysis=7')
    const input = await screen.findByLabelText('Failure threshold (plan target: 0.7)')
    expect(input).toHaveValue(0.7)
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => expect(runMcMock).toHaveBeenCalledTimes(1))
    expect(runMcMock.mock.calls[0][1]).toEqual({ num_trials: 2000, failure_rate_cap: 0.05, seed: null })
  })

  it('sends a shared threshold the user changed, and uses the same one for the Results check', async () => {
    const user = userEvent.setup()
    getWorkflowMock.mockResolvedValue(workflow(sharedPlanAt70))
    renderPage('/simulation/checks?analysis=7')
    const input = await screen.findByLabelText('Failure threshold (plan target: 0.7)')
    await user.click(screen.getByRole('button', { name: 'Check the plan' }))
    await waitFor(() => expect(runValidationMock).toHaveBeenCalledTimes(1))
    expect(runValidationMock.mock.calls[0][1]).toMatchObject({ mc_failure_threshold: 0.7 })
    await user.clear(input)
    await user.type(input, '0.75')
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => expect(runMcMock).toHaveBeenCalledTimes(1))
    expect(runMcMock.mock.calls[0][1]).toMatchObject({ failure_threshold: 0.75 })
  })

  it('explains shared Many variations with the STORED threshold, not the form (C5)', async () => {
    const user = userEvent.setup()
    const stored = { num_trials: 2000, failure_threshold: 0.85, failure_rate_cap: 0.05, failure_rate: 0, failure_rate_ci_lower: 0, failure_rate_ci_upper: 0.0019 }
    getWorkflowMock.mockResolvedValue(workflow({ mc: job('workflow_mc', { results: [{ ...mcRow, ...stored }, { ...mcRow, ...stored, time: '09:00-10:00' }] }) }))
    renderPage('/simulation/checks?analysis=7')
    const threshold = await screen.findByLabelText('Failure threshold (ρ)')
    expect(threshold).toHaveValue(0.75)
    const info = screen.getByRole('button', { name: 'What is Many variations?' })
    // N3 / K-UC-9: the ⓘ is not nested in the check's <summary>, and using it does not open or close the check.
    expect(info.closest('summary')).toBeNull()
    const check = info.closest('.check-line-frame')?.querySelector('details') as HTMLDetailsElement
    expect(check.querySelector('summary .check-line-info-slot')).not.toBeNull()
    const openBefore = check.open
    await user.click(info)
    expect(check.open).toBe(openBefore)
    await user.click(document.body)
    await user.hover(info)
    expect(screen.getByRole('tooltip')).toHaveTextContent('A version fails when Utilization Rate is above 85%.')
    await user.unhover(info)
    await user.clear(threshold)
    await user.type(threshold, '0.6')
    await user.hover(info)
    expect(screen.getByRole('tooltip')).toHaveTextContent('above 85%.')
    const chart = screen.getByTestId('many-variations-chart')
    // One row per period and no cashier name on a shared line.
    expect(within(chart).getAllByTestId('row-chart-row')).toHaveLength(2)
    expect(chart).toHaveTextContent('A variation fails when the counters’ Utilization Rate is above 85%.')
    expect(within(chart).getByTestId('mc-take')).toHaveTextContent('Closest to the 5% cap: 08:00-09:00, with 0% of 2,000 variations failing.')
    const table = screen.getByRole('region', { name: 'Monte Carlo simulation results by interval' })
    expect(within(table).getAllByRole('row')[1]).toHaveTextContent('0% – 0.19%')
    // The new SVG row chart is drawn (positive check; Plotly is no longer imported here).
    expect(within(chart).getByTestId('mc-chart')).toBeInTheDocument()
  })

  it('leaves out the Many variations explanation when the stored rows disagree', async () => {
    const stored = { num_trials: 2000, failure_rate_cap: 0.05 }
    getWorkflowMock.mockResolvedValue(workflow({ mc: job('workflow_mc', { results: [{ ...mcRow, ...stored, failure_threshold: 0.85 }, { ...mcRow, ...stored, time: '09:00-10:00', failure_threshold: 0.75 }] }) }))
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByTestId('many-variations-chart')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'What is Many variations?' })).not.toBeInTheDocument()
    expect(screen.getByTestId('many-variations-chart')).not.toHaveTextContent('A variation fails')
  })

  it('keeps the 0.75 default for a shared plan with no recorded target', async () => {
    const user = userEvent.setup()
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByLabelText('Failure threshold (ρ)')).toHaveValue(0.75)
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => expect(runMcMock).toHaveBeenCalledTimes(1))
    expect(runMcMock.mock.calls[0][1]).toMatchObject({ failure_threshold: 0.75 })
  })

  it('checks the plan from the full-day run when the server names that basis (OD-UX-13)', async () => {
    const user = userEvent.setup()
    getWorkflowMock.mockResolvedValue(workflow({ decision_basis: 'full_day_run', full_day_run_id: 31 }))
    const periods = [
      { time: '08:00-09:00', day_run_utilization: 0.91, target_utilization: 0.85, day_run: 'fail', variations_failure_rate: 0.01,
        variations_failure_cap: 0.05, variations: 'pass', verdict: 'fail' },
      { time: '09:00-10:00', day_run_utilization: 0.6, target_utilization: 0.85, day_run: 'pass', variations_failure_rate: 0.02,
        variations_failure_cap: 0.05, variations: 'pass', verdict: 'pass' },
    ]
    createDecisionMock.mockResolvedValueOnce({ decision: { status: 'revise', headline: 'Do not adopt Scenario "Plan A" yet.', recommendation: '',
      rationale: [], missing_evidence: [], scenario_id: 3, scenario_name: 'Plan A', dataset_id: 2, evidence_ids: {}, provenance_warning: '',
      basis: 'full_day_run', facts: { validation_intervals: 2, failed_intervals: 1, failed_periods: ['08:00-09:00'], insufficient_periods: [],
        periods, full_day_run: { id: 31, replications: 5, closing_policy: 'DRAIN', service_model: 'exponential' } } }, persisted: true })
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByTestId('decision-next-basis')).toHaveTextContent('Check the plan runs Many variations, then decides from full-day run 31 of this plan.')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    await waitFor(() => expect(createDecisionMock).toHaveBeenCalledTimes(1))
    expect(runMcMock).toHaveBeenCalledTimes(1)
    expect(runValidationMock).not.toHaveBeenCalled()
    expect(runMcMock.mock.invocationCallOrder[0]).toBeLessThan(createDecisionMock.mock.invocationCallOrder[0])
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent('Change the plan first. It did not hold up in: 08:00-09:00')
    expect(screen.getByTestId('decision-basis')).toHaveTextContent(
      'This Decision uses full-day run 31 (5 repeated days, closing rule: Finish serving customers already waiting) and Many variations.')
    const rows = within(screen.getByTestId('full-day-periods')).getAllByRole('row').slice(1)
    expect(rows.map((row) => row.textContent)).toEqual(['08:00-09:0091%85%1%Did not pass', '09:00-10:0060%85%2%Passed'])
  })

  it('names the periods a full-day Decision cannot tell yet', async () => {
    const user = userEvent.setup()
    getWorkflowMock.mockResolvedValue(workflow({ decision_basis: 'full_day_run', full_day_run_id: 31 }))
    createDecisionMock.mockResolvedValueOnce({ decision: { status: 'insufficient_evidence', headline: 'Insufficient evidence.', recommendation: '',
      rationale: [], missing_evidence: [], scenario_id: 3, scenario_name: 'Plan A', dataset_id: 2, evidence_ids: {}, provenance_warning: '',
      basis: 'full_day_run', facts: { failed_periods: [], insufficient_periods: ['09:00-10:00'] } }, persisted: true })
    renderPage('/simulation/checks?analysis=7')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent('Not enough checks yet. There is not enough data to tell in: 09:00-10:00')
  })

  it('says a stored shared Decision is out of date', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ decision: job('workflow_decision', { status: 'adopt' }), decision_stale: true }))
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent('Out of date. Your data or setup changed after this check.')
  })

  it('keeps a stored validation verdict bound to its saved cap when next-run settings change', async () => {
    const user = userEvent.setup()
    getWorkflowMock.mockResolvedValue(workflow({
      validation: job('workflow_validation', { results: [validationRow] }, { des_sim_hours: 24, mc_trials: 10000, mc_failure_threshold: 0.75, mc_failure_rate_cap: 0.05, seed: null }),
    }))
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByText(/Saved validation failure-rate cap: 5/)).toBeInTheDocument()
    expect(screen.getByText('Simulation validation passed.')).toBeInTheDocument()
    const cap = screen.getByLabelText('Failure rate cap')
    await user.clear(cap)
    await user.type(cap, '0.001')
    expect(screen.getByText('Simulation validation passed.')).toBeInTheDocument()
    expect(screen.getByText(/Run settings changed/)).toBeInTheDocument()
  })

  it('blocks invalid failure-rate settings before execution', async () => {
    const user = userEvent.setup()
    renderPage('/simulation/checks?analysis=7')
    const cap = await screen.findByLabelText('Failure rate cap')
    await user.clear(cap)
    await user.type(cap, '2')
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Failure rate cap must be between 0 and 1.')
    expect(runMcMock).not.toHaveBeenCalled()
  })

  it('names an unavailable selected plan and why instead of the generic guidance', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection_evidence: { scenario_id: 3, evidence_status: 'STALE_DATASET', evidence_reasons: [{ code: 'X', subject: 's', detail: 'Made with an older file.' }] } }))
    renderPage('/simulation/results?analysis=7&plan=suggested')
    expect(await screen.findByTestId('selection-unavailable')).toHaveTextContent('Made with an older file.')
    expect(screen.queryByText(/Choose a plan in Suggested plans \(Use this plan\)/)).not.toBeInTheDocument()
  })

  it('keeps the generic guidance when the reported status has no label', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection_evidence: { scenario_id: 3, evidence_status: 'SOMETHING_NEW', evidence_reasons: [] } }))
    renderPage('/simulation/results?analysis=7&plan=suggested')
    expect(await screen.findByText(/Choose a plan in Suggested plans \(Use this plan\)/)).toBeInTheDocument()
    expect(screen.queryByTestId('selection-unavailable')).not.toBeInTheDocument()
  })

  it('renders the approved Tagalog text', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
    renderPage('/simulation/results?analysis=7&plan=suggested', 'tl')
    expect(await screen.findByText(tl['simulation.select_scenario_first'], { exact: false })).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: en['nav.queue_simulation'] })).toBeInTheDocument()
    expect(en['simulation.run_full_operation']).toBe('Run full operation')
  })
})

describe('Current runs', () => {
  beforeEach(() => {
    getAnalysisMock.mockResolvedValue(setupOf('separate_queues'))
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
  })

  it('opens on Current when no plan is selected and runs the Current DES without claiming a plan', async () => {
    const user = userEvent.setup()
    runDesCurrentMock.mockImplementation(async () => {
      // The server now has the run; the page reads it back from the workflow evidence.
      getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null, des_current: job('workflow_des_current', trace, { scenario_id: null }) }))
      return { evidence: job('workflow_des_current', trace, { scenario_id: null }) }
    })
    renderPage()
    expect(await screen.findByRole('button', { name: 'Current' })).toHaveAttribute('aria-pressed', 'true')
    // Separate lines: the Current run is one continuous run without breaks (K-UC-3), never "period by period".
    expect(screen.queryByRole('button', { name: 'Run period by period' })).not.toBeInTheDocument()
    expect(screen.getByText('Not run yet. Use Run full operation.')).toBeInTheDocument()
    expect(screen.queryByText('Not run yet. Use Run period by period.')).not.toBeInTheDocument()
    expect(screen.getByText(en['simulation.run_basis_continuous_no_breaks'])).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run full operation' }))
    await waitFor(() => expect(runDesCurrentMock).toHaveBeenCalledTimes(1))
    expect(runDesCurrentMock).toHaveBeenCalledWith(7, { sim_hours: 24, queue_overload_threshold: 20, max_events: 3000, seed: null, carryover: true })
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()
    expect(runDesMock).not.toHaveBeenCalled()
    expect(runSelectedDesMock).not.toHaveBeenCalled()
  })

  it('does not claim the separate Current run drains the lines at closing (K-UC-12)', async () => {
    renderPage()
    const bar = await screen.findByRole('region', { name: en['simulation.run_bar'] })
    expect(await within(bar).findByRole('button', { name: 'Run full operation' })).toBeInTheDocument()
    expect(within(bar).queryByText(en['simulation.closing_rule_separate'])).not.toBeInTheDocument()
  })

  it('names the dataset Current would run on when no Current run exists', async () => {
    renderPage()
    expect(await screen.findByText('No current run for dataset #9.')).toBeInTheDocument()
  })

  it('shows no dataset number when the analysis has no valid current dataset', async () => {
    getAnalysisCurrentMock.mockRejectedValue(Object.assign(new Error('404'), { response: { status: 404 } }))
    renderPage()
    expect(await screen.findByTestId('run-status')).toHaveTextContent('Not run')
    await waitFor(() => expect(getAnalysisCurrentMock).toHaveBeenCalled())
    expect(screen.queryByText(/No current run for dataset/)).not.toBeInTheDocument()
  })

  it('does not look up the current dataset for a plan run', async () => {
    getAnalysisMock.mockResolvedValue(setupOf('shared_queue'))
    getWorkflowMock.mockResolvedValue(workflow())
    renderPage()
    await screen.findByRole('region', { name: 'Full-day run' })
    expect(getAnalysisCurrentMock).not.toHaveBeenCalled()
  })

  it('replays a separate Current run in the separate layout as one continuous run', async () => {
    const separateTrace = {
      ...trace,
      trace: [{ t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_id: 'queue_1', queue_len_after: 1 }],
      segments: [{ ...trace.segments[0], segment_id: 's1', queue_id: 'queue_1', c: 1, queue_structure: 'separate' }],
    }
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null, des_current: job('workflow_des_current', separateTrace, { scenario_id: null }) }))
    renderPage('/simulation/replay?analysis=7')
    expect(await screen.findByTestId('lane-queue_1')).toBeInTheDocument()
    expect(screen.getByText(en['simulation.one_run_notice_separate'])).toBeInTheDocument()
    expect(screen.queryByText('This run simulates one period at a time; it is not one continuous day.')).not.toBeInTheDocument()
  })

  it('gates the Results check on Many variations and shows the per-queue verdict', async () => {
    const user = userEvent.setup()
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByText('Current validation needs Current Monte Carlo evidence first.', { exact: false })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run Monte Carlo' }))
    await waitFor(() => expect(runMcCurrentMock).toHaveBeenCalledTimes(1))
    await user.click(await screen.findByRole('button', { name: 'Validate plan' }))
    await waitFor(() => expect(runValidationCurrentMock).toHaveBeenCalledTimes(1))
    expect(await screen.findByText('cashier-east')).toBeInTheDocument()
    expect(runMcMock).not.toHaveBeenCalled()
  })

  it('says the Current Results check is for separate lines only', async () => {
    getAnalysisMock.mockResolvedValue(setupOf('shared_queue'))
    renderPage('/simulation/checks?analysis=7&plan=current')
    expect(await screen.findByText('The results check of today\'s staffing is available for separate lines only.')).toBeInTheDocument()
    expect(runValidationCurrentMock).not.toHaveBeenCalled()
  })
})

describe('a selected separate-lines plan', () => {
  const v2scenario = {
    id: 9, name: 'Optimal @ 70%', dataset_id: 2, provenance: 'verified_snapshot',
    settings: { calculation: { schema_version: 2, engine_version: 'novaq-2026-09-separate-des-v2', options: { target_utilization: 0.85 } } },
  }
  const lane = {
    time: '08:00', queue_id: 'east-07', server_id: 'server:east-07', lambda: 4, lambda_routed: 5.8, mu: 11.4, c: 1, arrivals: 46, served: 45,
    waiting: 1, in_service: 0, abandoned: null, Wq_sim: 0.09, rho_sim: 0.55, max_queue: 4, active: true, simulation_supported: true, error: null,
    metric_provenance: 'simulated', customer_conservation: true,
  }
  const idle = { ...lane, queue_id: 'lane-A', server_id: 'server:lane-A', arrivals: 0, served: 0, Wq_sim: null, rho_sim: 0, max_queue: 0, active: false }
  function periodTrace(time: string, events: unknown[]) {
    return {
      results: [lane, idle], trace: events, trace_hours: 1, total_hours: 2, event_count: events.length, truncated: false, abandonment_supported: false,
      segments: [{ segment_id: `${time}:east-07`, time, queue_id: 'east-07', lambda: 4, mu: 11.4, c: 1, selected_model: 'Parallel M/G/1 (routing)',
        simulation_supported: true, error: null, queue_structure: 'separate', initial_queue_depth: 0, final_queue_depth: 0 }],
    }
  }
  const morning = [
    { t: 0.12, type: 'arrival', segment_id: '08:00', customer_id: 1, server_id: null, queue_id: 'east-07', queue_len_after: 1 },
    { t: 0.2, type: 'service_start', segment_id: '08:00', customer_id: 1, server_id: 'server:east-07', queue_id: 'east-07', queue_len_after: 0 },
    { t: 1.3, type: 'service_end', segment_id: '08:00', customer_id: 1, server_id: 'server:east-07', queue_id: 'east-07', queue_len_after: 0 },
  ]
  const later = [
    { t: 1.1, type: 'arrival', segment_id: '09:00', customer_id: 2, server_id: null, queue_id: 'east-07', queue_len_after: 1 },
    { t: 1.2, type: 'arrival', segment_id: '09:00', customer_id: 3, server_id: null, queue_id: 'lane-A', queue_len_after: 1 },
  ]
  const dayResult = {
    provenance: 'SELECTED', scenario_id: 9, analysis_id: 7, dataset_id: 2, seed: 42, duration_hours: 2,
    periods: [
      { time: '08:00', start_hours: 0, duration_hours: 1, active_queue_ids: ['east-07'], inactive_queue_ids: ['lane-A'], evaluation_status: 'FEASIBLE',
        conservation: true, total_lambda: 6, results: [lane, idle], trace: periodTrace('08:00', morning) },
      { time: '09:00', start_hours: 1, duration_hours: 1, active_queue_ids: ['east-07', 'lane-A'], inactive_queue_ids: [], evaluation_status: 'FEASIBLE',
        conservation: true, total_lambda: 6, results: [lane, idle], trace: periodTrace('09:00', later) },
    ],
    overall_conservation: true, overall_status: 'COMPLETED',
    summary: { basis: 'continuous_day', average_wait_hours: 0.09, longest_line: 4, arrivals: 92, served: 90, in_system_at_close: 2,
      periods: [{ time: '08:00', average_wait_hours: 0.09, longest_line: 4, arrivals: 46, served: 45 }, { time: '09:00', average_wait_hours: 0.09, longest_line: 4, arrivals: 46, served: 45 }] },
  }
  // B13: a per-date plan's selected run is one continuous day per date (periods labelled by date).
  const perDateResult = {
    ...dayResult,
    periods: ['2026-09-08', '2026-09-09'].flatMap((date) => dayResult.periods.map((period) => ({
      ...period, time: `${date} ${period.time} UTC`, trace: periodTrace(`${date} ${period.time} UTC`, period.trace.trace),
    }))),
    days: [
      { date: '2026-09-08', admitted: 46, served: 45, in_system_at_close: 1, customer_conservation: true, day_hours: 2 },
      { date: '2026-09-09', admitted: 46, served: 45, in_system_at_close: 1, customer_conservation: true, day_hours: 2 },
    ],
  }
  const daySetup = {
    event_period_basis: 'representative_day',
    segments: [{ id: '08:00', start_time: '08:00', end_time: '09:00', active_queue_ids: null }, { id: '09:00', start_time: '09:00', end_time: '10:00', active_queue_ids: null }],
    breaks: [{ queue_id: 'east-07', scheduled_start_time: '09:30', duration_minutes: 15 }],
  }
  const mcResult = { provenance: 'SELECTED', scenario_id: 9, des_job_id: 10, results: [{ ...mcRow, time: '08:00', queue_id: 'east-07', lambda: 5.75 }] }
  const validationResult = {
    provenance: 'SELECTED', scenario_id: 9, analysis_id: 7, dataset_id: 2, des_job_id: 10, mc_job_id: 11, failure_rate_cap: 0.05,
    periods: [{ time: '08:00', active_queue_ids: ['east-07'], status: 'pass', des_ok: true, des_reason: null,
      queues: [{ time: '08:00', queue_id: 'east-07', selected_model: 'Parallel M/G/1', mc_failure_rate: 0, mc_failure_rate_adequate: true,
        failure_rate_cap: 0.05, validation_verdict: 'pass', rho_sim: 0.55, Wq_sim: 0.09, served: 45 }] }],
    verdict: { status: 'pass', failed: [], inadequate: [], total: 1 },
  }
  const decision = {
    provenance: 'SELECTED', status: 'conditional', headline: 'Consider Scenario "Optimal @ 70%" conditionally.', recommendation: 'All checks passed.',
    rationale: ['Net lane change across periods: -1.'], missing_evidence: [], scenario_id: 9, scenario_name: 'Optimal @ 70%', dataset_id: 2,
    facts: { selected_target: 0.85, validation_checks: 1, failed_checks: 0, lane_delta: -1 }, failed_periods: [], inadequate_periods: [], evidence_ids: {},
  }

  function selected(overrides: Record<string, unknown> = {}, setup: Record<string, unknown> = daySetup) {
    getAnalysisMock.mockResolvedValue(setupOf('separate_queues', setup))
    getWorkflowMock.mockResolvedValue(workflow({ scenario: v2scenario, selection: job('workflow_selection', { scenario_id: 9 }), ...overrides }))
  }

  it('names the plan and runs it once with the default seed', async () => {
    const user = userEvent.setup()
    selected()
    runSelectedDesMock.mockResolvedValue({ evidence: job('workflow_des', dayResult, { scenario_id: 9 }) })
    renderPage()
    expect(await screen.findByText('Selected Plan: Optimal @ 70% (id 9)')).toBeInTheDocument()
    expect(screen.getByText('One continuous run of the day', { exact: false })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run full operation' }))
    await waitFor(() => expect(runSelectedDesMock).toHaveBeenCalledWith(7, { seed: 42 }))
    expect(runDesMock).not.toHaveBeenCalled()
    expect(optimizeSpy).not.toHaveBeenCalled()
  })

  it('points to Suggested plans when the selection went stale', async () => {
    getAnalysisMock.mockResolvedValue(setupOf('separate_queues'))
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: job('workflow_selection', { scenario_id: 9 }) }))
    renderPage('/simulation/results?analysis=7&plan=suggested')
    expect(await screen.findByText(/no longer matches the current analysis data/)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Run full operation' })).not.toBeInTheDocument()
  })

  it('shows the day totals from the server and the conservation check', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    renderPage()
    expect(await screen.findByRole('region', { name: 'Customer Served' })).toHaveTextContent('Suggested plan: 90')
    // B5: the plan's customers still in line at closing are an alert, not a two-sided card.
    expect(screen.queryByRole('region', { name: 'Still in line or being served at closing' })).not.toBeInTheDocument()
    expect(screen.getByTestId('closing-alert')).toHaveTextContent('2 customers still in line or being served at closing in the plan’s simulated day.')
    expect(screen.getByText("Customer counts match in every period.")).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Combined Waiting Line' })).toBeInTheDocument()
    expect(screen.getByText(/checked every 5 minutes/)).toBeInTheDocument()
    // The closing rule has one allowed value (drain_existing), so nothing offers to change it.
    expect(screen.getByText("At closing, staff finish serving customers already in line")).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Change' })).not.toBeInTheDocument()
    // One continuous day places the breaks in time: no break notice.
    expect(screen.queryByTestId('break-notice')).not.toBeInTheDocument()
  })

  it('places breaks in time for a per-date plan run one day per date (B13)', async () => {
    selected({ des: job('workflow_des', perDateResult, { scenario_id: 9 }) }, { ...daySetup, event_period_basis: 'per_date' })
    renderPage()
    expect(await within(await screen.findByRole('region', { name: en['simulation.run_bar'] })).findByText('One continuous run per date', { exact: false })).toBeInTheDocument()
    expect(screen.queryByTestId('break-notice')).not.toBeInTheDocument()
    expect(screen.getByTestId('dates-note')).toHaveTextContent('Customer totals add up all 2 dates; each date starts empty.')
  })

  it('still says a per-date run without operating segments understates breaks', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) }, { ...daySetup, event_period_basis: 'per_date', segments: [] })
    renderPage()
    expect(await screen.findByTestId('break-notice')).toHaveTextContent('Breaks are understated in runs with one period per calendar date')
  })

  it('says the Current run leaves the breaks out', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    renderPage('/simulation/results?analysis=7&plan=current')
    expect(await screen.findByTestId('break-notice')).toHaveTextContent('This run does not include the scheduled breaks in your setup')
    // K-UC-12: the Current run stops at closing; only the selected plan's run drains the lines.
    expect(screen.queryByText(en['simulation.closing_rule_separate'])).not.toBeInTheDocument()
  })

  it('shows no break notice when the setup has no breaks', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) }, { ...daySetup, event_period_basis: 'per_date', breaks: [] })
    renderPage('/simulation/results?analysis=7&plan=current')
    expect(await screen.findByTestId('run-status')).toBeInTheDocument()
    expect(screen.queryByTestId('break-notice')).not.toBeInTheDocument()
  })

  it('replays the whole day from the one execution on the store clock and keeps the time in the address', async () => {
    const user = userEvent.setup()
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    renderPage('/simulation/replay?analysis=7&t=08:15')
    expect(await screen.findByTestId('replay-clock')).toHaveTextContent('08:15')
    // The merged day is labelled with the day's hours, not the first period's.
    expect(screen.getByTestId('replay-period')).toHaveTextContent(/^08:00 - 10:00$/)
    // lane-A is opened only for 09:00, so at 08:15 it is not staffed; never shown as a break.
    expect(screen.getByTestId('state-lane-A')).toHaveTextContent('Closed / not staffed')
    expect(screen.getByRole('group', { name: 'Scheduled break (from your setup)' })).toHaveTextContent('east-07: 09:30–09:45')
    expect(screen.getByText('Break state unavailable for this run.')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Go to time'), { target: { value: '08:30' } })
    await user.click(screen.getByRole('button', { name: 'Go' }))
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('t=08%3A30'))
  })

  it('replays a per-date plan one whole date at a time and keeps the date in the address (B13)', async () => {
    const user = userEvent.setup()
    selected({ des: job('workflow_des', perDateResult, { scenario_id: 9 }) }, { ...daySetup, event_period_basis: 'per_date' })
    renderPage('/simulation/replay?analysis=7&t=08:15')
    expect(await screen.findByTestId('replay-clock')).toHaveTextContent('08:15')
    expect(screen.getByTestId('replay-period')).toHaveTextContent(/^2026-09-08 · 08:00 - 10:00$/)
    await user.selectOptions(screen.getByLabelText('Date'), '2026-09-09')
    expect(screen.getByTestId('where')).toHaveTextContent('date=2026-09-09')
    expect(screen.getByTestId('where')).not.toHaveTextContent('t=')
    expect(screen.getByTestId('replay-period')).toHaveTextContent(/^2026-09-09 · /)
  })

  it('replays a per-date plan without operating segments one period at a time', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) }, { ...daySetup, event_period_basis: 'per_date', segments: [] })
    renderPage('/simulation/replay?analysis=7')
    expect(await screen.findByText('This run simulates one period at a time; it is not one continuous day.')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Period' })).toBeInTheDocument()
  })

  it('checks the plan: Many variations, Results check, then the Decision, in that order', async () => {
    const user = userEvent.setup()
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    runSelectedMcMock.mockResolvedValue({ evidence: job('workflow_mc', mcResult, { scenario_id: 9 }) })
    runSelectedValidationMock.mockResolvedValue({ evidence: job('workflow_validation', validationResult, { scenario_id: 9 }) })
    runSelectedDecisionMock.mockResolvedValue({ decision, persisted: true, evidence: job('workflow_decision', decision, { scenario_id: 9 }) })
    renderPage('/simulation/checks?analysis=7')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    await waitFor(() => expect(runSelectedDecisionMock).toHaveBeenCalledTimes(1))
    const order = [runSelectedMcMock, runSelectedValidationMock, runSelectedDecisionMock].map((mock) => mock.mock.invocationCallOrder[0])
    expect(order).toEqual([...order].sort((a, b) => a - b))
    expect(runSelectedMcMock.mock.calls[0][1]).not.toHaveProperty('failure_threshold')
    expect(await screen.findByText('Decision: CONDITIONAL')).toBeInTheDocument()
    expect(screen.getByTestId('decision-plain')).toHaveTextContent('Saved checks passed for this run. Savings cannot be compared. Review the estimated loads and costs before using the plan.')
    expect(screen.getByTestId('decision-plain').parentElement).toHaveClass('alert-warn')
    expect(screen.getByTestId('selected-decision-scope')).toBeVisible()
    expect(screen.getByTestId('selected-decision-scope').closest('details')).toBeNull()
    expect(screen.getByTestId('selected-decision-scope')).toHaveTextContent('Load estimate uncertainty: Not checked.')
    // U10 F15: the evidence row says what the numbers count.
    expect(screen.getByRole('row', { name: /Checks that did not pass/ })).toHaveTextContent('0 of 1')
    expect(screen.getByRole('link', { name: 'Continue to Reports' })).toHaveAttribute('href', '/reports?analysis=7')
    // Each period's lane table scrolls in its own box, so a phone never scrolls the page sideways.
    expect(screen.getByRole('region', { name: 'Period evidence · 08:00' })).toContainElement(screen.getByRole('rowheader', { name: 'east-07' }))
  })

  it('stops the sequence at the first refusal and shows the server reason', async () => {
    const user = userEvent.setup()
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    runSelectedMcMock.mockRejectedValue(Object.assign(new Error('409'), { response: { status: 409, data: { detail: 'The plan changed.' } } }))
    renderPage('/simulation/checks?analysis=7')
    await user.click(await screen.findByRole('button', { name: 'Check the plan' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('The plan changed.')
    expect(runSelectedValidationMock).not.toHaveBeenCalled()
    expect(runSelectedDecisionMock).not.toHaveBeenCalled()
  })

  it('needs a run before the checks, and validation before the decision', async () => {
    selected()
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByRole('button', { name: 'Check the plan' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Run validation' })).toBeDisabled()
    expect(screen.getByRole('button', { name: 'Run decision' })).toBeDisabled()
  })

  it('warns and sends the threshold when it is set below the plan target', async () => {
    const user = userEvent.setup()
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    runSelectedMcMock.mockResolvedValue({ evidence: job('workflow_mc', mcResult, { scenario_id: 9 }) })
    renderPage('/simulation/checks?analysis=7')
    const input = await screen.findByLabelText('Failure threshold (plan target: 0.85)')
    await user.clear(input)
    await user.type(input, '0.75')
    expect(screen.getByText(/below the plan target/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Run selected MC' }))
    await waitFor(() => expect(runSelectedMcMock.mock.calls[0][1]).toMatchObject({ failure_threshold: 0.75 }))
  })

  it('restores a stored decision without rerunning anything', async () => {
    selected({
      des: job('workflow_des', dayResult, { scenario_id: 9 }), mc: job('workflow_mc', mcResult, { scenario_id: 9 }),
      validation: job('workflow_validation', validationResult, { scenario_id: 9 }), decision: job('workflow_decision', { ...decision, status: 'revise', failed_periods: ['10:00'] }, { scenario_id: 9 }),
    })
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByText('Decision: REVISE')).toBeInTheDocument()
    expect(screen.getByTestId('decision-plain')).toHaveTextContent('This saved run did not pass in 10:00. Review the plan and estimated loads.')
    expect(screen.getByRole('link', { name: 'Return to Suggested plans' })).toHaveAttribute('href', '/analyses/7/plans')
    expect(runSelectedDecisionMock).not.toHaveBeenCalled()
  })

  it('shows the operating hours as a 24-hour chip, in English and Tagalog (A6)', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    const { unmount } = renderPage()
    const chip = (await screen.findByText('Operating hours: 08:00 - 10:00.')).closest('.hours-chip')
    expect(chip).not.toBeNull()
    expect(chip?.querySelector('svg')).toHaveAttribute('aria-hidden', 'true')
    unmount()
    renderPage('/simulation/results?analysis=7', 'tl')
    expect(await screen.findByText(tl['simulation.operating_hours'].replace('{{hours}}', '08:00 - 10:00'))).toBeInTheDocument()
  })

  it('gives the Combined Waiting Line a legend with Breaks only when the Setup has breaks (A7)', async () => {
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    const { unmount } = renderPage()
    const legend = await screen.findByTestId('waiting-legend')
    expect(within(legend).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Combined Waiting Line', 'Breaks'])
    expect(screen.queryByText(en['simulation.chart_breaks_marked'], { exact: false })).not.toBeInTheDocument()
    unmount()
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) }, { ...daySetup, breaks: [] })
    renderPage()
    expect(within(await screen.findByTestId('waiting-legend')).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Combined Waiting Line'])
  })

  it('explains Wq and ρ on the More results lane tables by hover, focus and click; Escape closes (A8)', async () => {
    const user = userEvent.setup()
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }) })
    renderPage()
    const [wq] = await screen.findAllByRole('button', { name: 'Wq (min)' })
    await user.hover(wq)
    expect(screen.getByRole('tooltip')).toHaveTextContent(en['simulation.tip_wq'])
    await user.unhover(wq)
    await waitFor(() => expect(screen.queryByRole('tooltip')).not.toBeInTheDocument())
    const [rho] = screen.getAllByRole('button', { name: 'ρ' })
    rho.focus()
    expect(await screen.findByRole('tooltip')).toHaveTextContent(en['simulation.tip_rho'])
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
    await user.click(wq)
    expect(wq).toHaveAttribute('aria-expanded', 'true')
    await user.click(wq)
    expect(wq).toHaveAttribute('aria-expanded', 'false')
  })

  it('draws a stored separate Many variations run against its cap and names the highest-risk cashier (B7, B8)', async () => {
    const user = userEvent.setup()
    const stored = { num_trials: 2000, failure_threshold: 0.85, failure_rate_cap: 0.05, arrival_noise_fraction: 0.2, service_noise_fraction: 0.1 }
    const rows = [
      { ...mcRow, ...stored, time: '08:00', queue_id: 'east-07', failure_rate: 0, failure_rate_ci_lower: 0, failure_rate_ci_upper: 0.0019 },
      { ...mcRow, ...stored, time: '08:00', queue_id: 'lane-A', failure_rate: 0.003, failure_rate_ci_lower: 0.0014, failure_rate_ci_upper: 0.0065 },
      { ...mcRow, ...stored, time: '09:00', queue_id: 'east-07', failure_rate: 0.0019, failure_rate_ci_lower: 0, failure_rate_ci_upper: 0.004 },
    ]
    selected({ des: job('workflow_des', dayResult, { scenario_id: 9 }), mc: job('workflow_mc', { ...mcResult, results: rows }, { scenario_id: 9, seed: 42 }) })
    renderPage('/simulation/checks?analysis=7')
    const chart = await screen.findByTestId('many-variations-chart')
    expect(within(chart).getByTestId('mc-take')).toHaveTextContent('Closest to the 5% cap: 08:00, lane-A, with 0.3% of 2,000 variations failing.')
    expect(within(chart).getAllByTestId('row-chart-row')).toHaveLength(2)
    expect(within(chart).getByTestId('row-chart-reference')).toHaveTextContent('5%')
    // The stored threshold is the plan's target, so the chip may say so.
    expect(chart).toHaveTextContent('A variation fails when a cashier’s Utilization Rate is above 85%, the plan’s target.')
    // Tap (here: click) a row to see every cashier of that period.
    await user.click(within(chart).getAllByTestId('row-chart-row')[0])
    const detail = within(chart).getByTestId('mc-detail')
    expect(within(detail).getAllByRole('row').slice(1).map((row) => row.textContent)).toEqual(['east-070%0% – 0.19%', 'lane-A0.3%0.14% – 0.65%'])
    // The stored table now prints percentages with the decimal rule.
    const table = screen.getByRole('region', { name: 'Monte Carlo' })
    expect(within(table).getAllByRole('row')[3]).toHaveTextContent('0.19%')
    const info = screen.getByRole('button', { name: 'What is Many variations?' })
    await user.hover(info)
    expect(screen.getByRole('tooltip')).toHaveTextContent('NovaQ calculates 2,000 what-if versions of each period')
    expect(screen.getByRole('tooltip')).toHaveTextContent('above 85%. The period passes when no more than 5% of versions fail.')
    expect(within(chart).getByTestId('mc-chart')).toBeInTheDocument()
  })

  it('never shows another plan\'s stored run', async () => {
    selected({ des: job('workflow_des', { ...dayResult, scenario_id: 99 }, { scenario_id: 99 }) })
    renderPage()
    expect(await screen.findByTestId('run-status')).toHaveTextContent('Not run')
    expect(screen.getByRole('region', { name: 'Average wait' })).toHaveTextContent('Suggested plan: Not run')
  })
})

describe('the continuous full-day run (B4a preview)', () => {
  it('asks for the closing rule first and saves the choice for future runs', async () => {
    const user = userEvent.setup()
    getClosingPolicyMock.mockResolvedValue({ closing_policy: null, choices: [] })
    getCompatibilityMock.mockResolvedValue(compatibility({
      plans: { current: { ...compatiblePlan, compatible: false, reasons: [{ code: 'no_closing_policy' }] },
        suggested: { ...compatiblePlan, compatible: false, reasons: [{ code: 'no_closing_policy' }] } },
    }, null))
    renderPage()
    const choice = await screen.findByTestId('closing-choice')
    expect(choice).toHaveTextContent('Choose what happens at closing time first.')
    expect(screen.getByRole('button', { name: 'Run full operation' })).toBeDisabled()
    // U10 F6: each option has its title before what it means.
    expect(within(choice).getByRole('radio', { name: /^Finish serving customers already waiting — counters on duty keep serving/ })).toBeInTheDocument()
    expect(within(choice).getByRole('radio', { name: /^Stop service at closing — customers still waiting are not served/ })).toBeInTheDocument()
    await user.click(within(choice).getByRole('radio', { name: /keep serving everyone already in line/ }))
    await user.click(within(choice).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(putClosingPolicyMock).toHaveBeenCalledWith(7, 'DRAIN'))
  })

  it('shows the saved rule with a Change link, the hours and the preview label', async () => {
    renderPage()
    expect(await screen.findByTestId('closing-rule')).toHaveTextContent('At closing time: counters on duty keep serving everyone already in line.')
    expect(screen.getByRole('button', { name: 'Change' })).toBeInTheDocument()
    const bar = screen.getByRole('region', { name: 'Full-day run' })
    expect(bar).toHaveTextContent('Operating hours: 08:00 - 10:00.')
    expect(bar).toHaveTextContent('Simulated · preview')
    expect(bar).toHaveTextContent('About 13 customers per day.')
    // Contextual help (plan U8).
    expect(within(bar).getByRole('link', { name: 'Help: Full-day run and period-by-period run' })).toHaveAttribute('href', '/help/simulation#methods')
    expect(screen.getByRole('link', { name: 'Help: Queue Simulation' })).toHaveAttribute('href', '/help/simulation')
  })

  it('asks the two unanswered Setup questions instead of blaming features the user never turned on (U10 F12)', async () => {
    getCompatibilityMock.mockResolvedValue(compatibility({
      plans: { current: { ...compatiblePlan, compatible: false, reasons: [{ code: 'capacity_or_abandonment_unknown' }] },
        suggested: { ...compatiblePlan, compatible: false, reasons: [{ code: 'capacity_or_abandonment_unknown' }] } },
    }))
    renderPage()
    const refusal = await screen.findByTestId('continuous-refusal')
    expect(refusal).toHaveTextContent('You can save now. The full-day run stays unavailable until you answer.')
    expect(refusal).not.toHaveTextContent('capacity_or_abandonment_unknown')
  })

  it.each(['capacity_or_abandonment', 'capacity_or_abandonment_unknown'])(
    'opens local Advanced settings for %s without enabling the run', async (code) => {
      getAnalysisMock.mockResolvedValue(setupOf('shared_queue', { capacity_mode: 'unknown', abandonment_mode: 'unknown' }))
      getCompatibilityMock.mockResolvedValue(compatibility({
        plans: { current: { ...compatiblePlan, horizon: null, compatible: false, reasons: [{ code }] },
          suggested: { ...compatiblePlan, horizon: null, compatible: false, reasons: [{ code }] } },
      }))
      renderPage('/simulation/replay?analysis=7')
      const refusal = await screen.findByTestId('continuous-refusal')
      await userEvent.setup().click(within(refusal).getByRole('button', { name: 'Open Advanced settings' }))
      const capacity = screen.getByRole('radio', { name: 'No known limit' })
      expect(capacity.closest('details')).toHaveAttribute('open')
      expect(document.activeElement).toBe(capacity)
      const bar = screen.getByRole('region', { name: 'Full-day run' })
      expect(bar).toHaveTextContent('Operating hours: Unavailable')
      expect(bar).not.toHaveTextContent('Operating hours: not set')
      expect(screen.getByRole('button', { name: 'Run full operation' })).toBeDisabled()
      expect(createContinuousRunMock).not.toHaveBeenCalled()
      expect(getContinuousPlaybackMock).not.toHaveBeenCalled()
    },
  )

  it('opens model choices directly from the repair link', async () => {
    getAnalysisMock.mockResolvedValue(setupOf('shared_queue', { capacity_mode: 'unknown', abandonment_mode: 'unknown' }))
    renderPage('/simulation/results?analysis=7&plan=current&advanced=model')
    const capacity = await screen.findByRole('radio', { name: 'No known limit' })
    await waitFor(() => expect(capacity.closest('details')).toHaveAttribute('open'))
    expect(document.activeElement).toBe(capacity)
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('blocks Run throughout a settings save and waits for refreshed compatibility', async () => {
    const initial = setupOf('shared_queue', { capacity_mode: 'unlimited', abandonment_mode: 'not_modeled' })
    getAnalysisMock.mockResolvedValue(initial)
    let finish!: (result: unknown) => void
    const pending = new Promise((resolve) => { finish = resolve })
    patchAnalysisMock.mockReturnValue(pending)
    renderPage('/simulation/results?analysis=7&plan=current&advanced=model')
    const user = userEvent.setup()
    const run = await screen.findByRole('button', { name: 'Run full operation' })
    await user.click(await screen.findByRole('radio', { name: "I'm not sure" }))
    expect(run).toBeDisabled()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledTimes(1))
    expect(run).toBeDisabled()
    await user.click(run)
    expect(createContinuousRunMock).not.toHaveBeenCalled()
    const unknown = setupOf('shared_queue', { capacity_mode: 'unknown', abandonment_mode: 'not_modeled' })
    getAnalysisMock.mockResolvedValue(unknown)
    getCompatibilityMock.mockResolvedValue(compatibility({ plans: {
      current: { ...compatiblePlan, compatible: false, reasons: [{ code: 'capacity_or_abandonment_unknown' }] },
      suggested: compatiblePlan,
    } }))
    await act(async () => { finish(unknown); await pending })
    await screen.findByTestId('continuous-refusal')
    expect(screen.getByRole('button', { name: 'Run full operation' })).toBeDisabled()
    expect(createContinuousRunMock).not.toHaveBeenCalled()
  })

  it('names why a shared line cannot run the full day without substituting the older replay', async () => {
    getCompatibilityMock.mockResolvedValue(compatibility({
      plans: { current: { ...compatiblePlan, compatible: false, reasons: [{ code: 'service_time_variation' }] },
        suggested: { ...compatiblePlan, compatible: false, reasons: [{ code: 'timeline_invalid', problems: ['09:00 to 09:30 is not covered.'] }] } },
    }))
    renderPage()
    const refusal = await screen.findByTestId('continuous-refusal')
    expect(refusal).toHaveTextContent('The periods do not form one operating day:')
    expect(refusal).toHaveTextContent('09:00 to 09:30 is not covered.')
    expect(screen.getByRole('button', { name: 'Run full operation' })).toBeDisabled()
    expect(screen.queryByRole('button', { name: 'Run period by period' })).not.toBeInTheDocument()
    expect(screen.queryByRole('region', { name: 'Period-by-period run (older method)' })).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Current' }))
    expect(await screen.findByTestId('continuous-refusal')).toHaveTextContent('not the service time of every customer')
  })

  it('says which service times a run uses and names borrowed periods and plan gaps', async () => {
    getCompatibilityMock.mockResolvedValue(compatibility({
      plans: {
        current: { ...compatiblePlan, service_model: 'recorded', service_fallbacks: [{ period_id: 's3', uses_period_id: 's2' }] },
        suggested: { ...compatiblePlan, compatible: false, service_model: 'recorded',
          reasons: [{ code: 'plan_missing_periods', periods: ['s3'] }] },
      },
    }))
    renderPage()
    const refusal = await screen.findByTestId('continuous-refusal')
    expect(refusal).toHaveTextContent('The selected plan has no counter count for periods without customers in the data: s3')
    // A refused run says nothing about how it would have served customers.
    expect(screen.queryByTestId('continuous-service')).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Current' }))
    await waitFor(() => expect(screen.getByTestId('continuous-service')).toHaveTextContent(
      'Uses your recorded service times. No customers were recorded in some periods, so service there uses the nearest recorded period: s3 uses s2.'))
    expect(screen.queryByTestId('continuous-refusal')).not.toBeInTheDocument()
  })

  it('says how many counter breaks a run includes, and nothing when it is refused (B4c)', async () => {
    getCompatibilityMock.mockResolvedValue(compatibility({
      plans: { current: { ...compatiblePlan, counter_breaks: 2 },
        suggested: { ...compatiblePlan, compatible: false, counter_breaks: 2, scenario_id: 3, scenario_name: 'Plan A',
          reasons: [{ code: 'breaks_not_staffed', problems: ['Break at 09:00 needs a counter, but this staffing has 1 counter(s) and 2 break(s) at 09:00.'] }] } },
    }))
    renderPage()
    const refusal = await screen.findByTestId('continuous-refusal')
    expect(refusal).toHaveTextContent('A counter break cannot be covered by this staffing:')
    expect(refusal).toHaveTextContent('Break at 09:00 needs a counter')
    expect(screen.queryByTestId('continuous-breaks')).not.toBeInTheDocument()
    await userEvent.setup().click(screen.getByRole('button', { name: 'Current' }))
    await waitFor(() => expect(screen.getByTestId('continuous-breaks')).toHaveTextContent(
      'Includes 2 counter break(s) from the Setup, each taken by the first free counter.'))
  })

  it('says a counts-per-period run uses estimated service times', async () => {
    getCompatibilityMock.mockResolvedValue(compatibility({
      plans: { current: { ...compatiblePlan, service_model: 'exponential' },
        suggested: { ...compatiblePlan, service_model: 'exponential', scenario_id: 3, scenario_name: 'Plan A' } },
    }))
    renderPage()
    expect(await screen.findByTestId('continuous-service')).toHaveTextContent('Uses estimated service times (counts per period).')
  })

  it('runs the chosen plan once with automatic defaults and no repetition field', async () => {
    const user = userEvent.setup()
    createContinuousRunMock.mockResolvedValue(continuousRun(21, 'suggested'))
    renderPage()
    const button = await screen.findByRole('button', { name: 'Run full operation' })
    const bar = button.closest('section') as HTMLElement
    await user.click(within(bar).getByText('Advanced settings', { exact: true }))
    expect(within(bar).queryByLabelText('Repeated days')).not.toBeInTheDocument()
    expect(within(bar).getByLabelText('Random seed')).toBeInTheDocument()
    await user.click(button)
    await waitFor(() => expect(createContinuousRunMock).toHaveBeenCalledWith(7, { plan: 'suggested', replications: 5, seed: 42 }))
    expect(runDesMock).not.toHaveBeenCalled()
    expect(optimizeSpy).not.toHaveBeenCalled()
  })

  it('reloads the workflow after a full-day run, which changes the Decision basis (OD-UX-13)', async () => {
    const user = userEvent.setup()
    createContinuousRunMock.mockResolvedValue(continuousRun(21, 'suggested'))
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Run full operation' }))
    await waitFor(() => expect(createContinuousRunMock).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(getWorkflowMock.mock.invocationCallOrder.some(
      (order) => order > createContinuousRunMock.mock.invocationCallOrder[0])).toBe(true))
  })

  it('automatically fits the default repetitions to the server customer budget', async () => {
    const user = userEvent.setup()
    createContinuousRunMock.mockResolvedValue(continuousRun(21, 'suggested'))
    getCompatibilityMock.mockResolvedValue(compatibility({ plans: { current: compatiblePlan, suggested: { ...compatiblePlan, expected_customers_per_day: 600 } } }))
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Run full operation' }))
    await waitFor(() => expect(createContinuousRunMock).toHaveBeenCalledWith(7, { plan: 'suggested', replications: 4, seed: 42 }))
    expect(createContinuousRunMock).toHaveBeenCalledTimes(1)
  })

  it('refuses a day that cannot fit once, without changing demand or submitting a run', async () => {
    const user = userEvent.setup()
    getCompatibilityMock.mockResolvedValue(compatibility({ plans: { current: compatiblePlan, suggested: { ...compatiblePlan, expected_customers_per_day: 3000 } } }))
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Run full operation' }))
    expect(screen.getByRole('alert')).toHaveTextContent('This run would have 3000 expected customers, above the limit of 2900.')
    expect(createContinuousRunMock).not.toHaveBeenCalled()
  })

  it('rounds the expected customers in the refusal to one decimal, as the API does (K-UC-15)', async () => {
    const user = userEvent.setup()
    getCompatibilityMock.mockResolvedValue(compatibility({ plans: { current: compatiblePlan, suggested: { ...compatiblePlan, expected_customers_per_day: 3012.4567 } } }))
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Run full operation' }))
    expect(screen.getByRole('alert')).toHaveTextContent('This run would have 3012.5 expected customers, above the limit of 2900.')
    expect(screen.getByRole('alert')).not.toHaveTextContent('3012.4567')
    expect(createContinuousRunMock).not.toHaveBeenCalled()
  })

  it('shows both stored runs on the cards and under More results, from their own summaries', async () => {
    listContinuousRunsMock.mockResolvedValue({ runs: [
      { id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN', setup_matches_current: true, dataset_is_current: true, plan_is_selected: true },
      { id: 30, plan: 'current', replications: 5, seed: 42, closing_policy: 'DRAIN', setup_matches_current: true, dataset_is_current: true, plan_is_selected: null },
      { id: 12, plan: 'current', replications: 5, seed: 1, closing_policy: 'DRAIN', setup_matches_current: true, dataset_is_current: true, plan_is_selected: null },
    ] })
    getContinuousRunMock.mockImplementation(async (_analysis: number, runId: number) => (runId === 31
      ? continuousRun(31, 'suggested', { waitHours: 0.05, served: 13 }) : continuousRun(runId, 'current', { waitHours: 0.1, served: 11 })))
    renderPage()
    const cards = await screen.findByRole('group', { name: 'Full-day key results' })
    await waitFor(() => expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Current: 6 min (3 min–6 min)'))
    expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Suggested plan: 3 min (3 min–6 min)')
    // C3 + OD-2: Average wait, Longest Single Line and the kept Not served at closing card; Customer Served moved.
    expect(within(cards).getAllByRole('region').map((region) => region.getAttribute('aria-label'))).toEqual(['Average wait', 'Longest Single Line', 'Not served at closing'])
    expect(within(cards).getByRole('region', { name: 'Not served at closing' })).toHaveTextContent('Suggested plan: 0')
    expect(getContinuousRunMock).not.toHaveBeenCalledWith(7, 12)
    expect(await screen.findByRole('heading', { name: 'People waiting through the day' })).toBeInTheDocument()
    const served = screen.getByRole('region', { name: 'Customer Served' })
    expect(served.closest('details')).not.toBeNull()
    expect(served).toHaveTextContent('Current: 11 (10–16)')
    expect(served).toHaveTextContent('Suggested plan: 13 (10–16)')
    expect(screen.getByText('The charts show repeated day 1 of 5.')).toBeInTheDocument()
    expect(getContinuousPlaybackMock).toHaveBeenCalledWith(7, 31, 0)
    const byPeriod = screen.getByRole('region', { name: 'Day 1 by period' })
    expect(within(within(byPeriod).getByRole('row', { name: /08:00-09:00/ })).getAllByRole('cell').map((cell) => cell.textContent)).toEqual(['2', '2', '0', '3 min'])
    expect(within(byPeriod).getByRole('row', { name: /09:00-10:00/ })).toHaveTextContent('Unavailable')
    // U10 F7: the caption names the statistic; F8: no warning when both runs used the same closing rule.
    expect(screen.getByText(/Average wait counts every customer served on the repeated days \(5\)/)).toBeInTheDocument()
    expect(screen.queryByTestId('continuous-rules-differ')).not.toBeInTheDocument()
  })

  it('says when the two runs used different closing rules (U10 F8)', async () => {
    listContinuousRunsMock.mockResolvedValue({ runs: [
      { id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'HARD_CUTOFF', setup_matches_current: true, dataset_is_current: true, plan_is_selected: true },
      { id: 30, plan: 'current', replications: 5, seed: 42, closing_policy: 'DRAIN', setup_matches_current: true, dataset_is_current: true, plan_is_selected: null },
    ] })
    getContinuousRunMock.mockImplementation(async (_analysis: number, runId: number) => {
      if (runId !== 31) return continuousRun(runId, 'current')
      const run = continuousRun(31, 'suggested')
      return { ...run, evidence: { ...run.evidence, params: { ...run.evidence.params, closing_policy: 'HARD_CUTOFF' } } }
    })
    renderPage()
    expect(await screen.findByTestId('continuous-rules-differ')).toHaveTextContent(
      'These two runs used different closing rules (Current: closing rule: serve everyone in line; Suggested plan: closing rule: stop at closing).')
  })

  it('says when the Setup, the data or the plan changed after a stored run', async () => {
    listContinuousRunsMock.mockResolvedValue({ runs: [{ id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN',
      setup_matches_current: false, dataset_is_current: false, plan_is_selected: false }] })
    getContinuousRunMock.mockResolvedValue(continuousRun(31, 'suggested', { extra: { setup_matches_current: false, dataset_is_current: false, plan_is_selected: false } }))
    renderPage()
    expect(await screen.findByText('Data and setup changed after this run.')).toBeInTheDocument()
    expect(screen.getByText('The planning file changed after this run.')).toBeInTheDocument()
    expect(screen.getByText('This run used a plan that is no longer selected.')).toBeInTheDocument()
  })

  it('replays a repeated day on the store clock from its own events', async () => {
    const user = userEvent.setup()
    listContinuousRunsMock.mockResolvedValue({ runs: [{ id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN',
      setup_matches_current: true, dataset_is_current: true, plan_is_selected: true }] })
    getContinuousRunMock.mockResolvedValue(continuousRun(31, 'suggested'))
    renderPage('/simulation/replay?analysis=7')
    expect(await screen.findByTestId('continuous-clock')).toHaveTextContent('08:00')
    const replay = screen.getByRole('region', { name: 'Full-day replay' })
    fireEvent.change(within(replay).getByLabelText('Go to time'), { target: { value: '08:33' } })
    await user.click(within(replay).getByRole('button', { name: 'Go' }))
    expect(screen.getByTestId('continuous-clock')).toHaveTextContent('08:33')
    const state = screen.getByTestId('continuous-state')
    expect(state).toHaveTextContent('Waiting: 1')
    expect(state).toHaveTextContent('Counters serving: 1')
    expect(state).toHaveTextContent('Arrived so far: 2')
    expect(state).toHaveTextContent('Served so far: 0')
    await user.selectOptions(within(replay).getByLabelText('Repeated day'), '3')
    await waitFor(() => expect(getContinuousPlaybackMock).toHaveBeenCalledWith(7, 31, 3))
  })

  it('plays the day on simulated time: one simulated minute per second at 1x, whatever the day length (D29)', async () => {
    listContinuousRunsMock.mockResolvedValue({ runs: [{ id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN',
      setup_matches_current: true, dataset_is_current: true, plan_is_selected: true }] })
    getContinuousRunMock.mockResolvedValue(continuousRun(31, 'suggested'))
    renderPage('/simulation/replay?analysis=7')
    expect(await screen.findByTestId('continuous-clock')).toHaveTextContent('08:00')
    const replay = screen.getByRole('region', { name: 'Full-day replay' })
    vi.useFakeTimers({ toFake: ['setInterval', 'clearInterval'] })
    try {
      fireEvent.click(within(replay).getByRole('button', { name: 'Play' }))
      act(() => { vi.advanceTimersByTime(3000) })
      // The day is 2 hours long; the old rule (whole day in 60 s) would show 08:06 here.
      expect(screen.getByTestId('continuous-clock')).toHaveTextContent('08:03')
      fireEvent.change(within(replay).getByLabelText('Speed'), { target: { value: '10' } })
      act(() => { vi.advanceTimersByTime(3000) })
      expect(screen.getByTestId('continuous-clock')).toHaveTextContent('08:33')
      act(() => { vi.advanceTimersByTime(60000) })
      expect(screen.getByTestId('continuous-clock')).toHaveTextContent('10:00')
      expect(within(replay).getByRole('button', { name: 'Play' })).toBeInTheDocument()
    } finally {
      vi.useRealTimers()
    }
  })

  it('states the full-day Decision rule and shows the ranges (OD-UX-13)', async () => {
    listContinuousRunsMock.mockResolvedValue({ runs: [{ id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN',
      setup_matches_current: true, dataset_is_current: true, plan_is_selected: true }] })
    getContinuousRunMock.mockResolvedValue(continuousRun(31, 'suggested'))
    renderPage('/simulation/checks?analysis=7')
    expect(await screen.findByTestId('continuous-decision-rule')).toHaveTextContent(
      "a period passes when its average busy share over the repeated days is at or below the plan's target and Many variations holds up")
    const ranges = await screen.findByRole('region', { name: 'Ranges across the repeated days (average, lowest–highest)' })
    expect(ranges).toHaveTextContent('Counter utilization during opening hours62% (50%–70%)')
  })

  it('is not offered for separate lines', async () => {
    getAnalysisMock.mockResolvedValue(setupOf('separate_queues'))
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
    renderPage()
    await screen.findByTestId('run-status')
    expect(screen.queryByRole('region', { name: 'Full-day run' })).not.toBeInTheDocument()
    expect(getCompatibilityMock).not.toHaveBeenCalled()
  })
})
