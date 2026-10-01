import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Link, Route, Routes } from 'react-router-dom'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../test/test-utils'
import { queryClient as appQueryClient } from '../lib/queryClient'
import { AnalysisSetupPage } from './AnalysisSetupPage'
import { OptimizePage } from './OptimizePage'
import { SimulationPage } from './SimulationPage'
import { DecisionEndpointPage } from '../components/analysis/DecisionEndpointPage'

// Every workflow job records the Setup it was computed for, and the server stops serving it once
// the Setup changes. A Setup save or a break apply must therefore never leave the previous Setup's
// cached workflow evidence on screen, not even while the fresh workflow request is in flight.

const getWorkflowMock = vi.fn()
const getAnalysisMock = vi.fn()
const getAnalysisCurrentMock = vi.fn()
const listAnalysisDatasetsMock = vi.fn()
const patchAnalysisMock = vi.fn()
const listDatasetsMock = vi.fn()
const optimizeSeparateBreaksMock = vi.fn()
const applySeparateBreaksMock = vi.fn()
const unexpectedCall = vi.fn()

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  runWorkflowDes: (...args: unknown[]) => unexpectedCall(...args),
  runWorkflowDesCurrent: (...args: unknown[]) => unexpectedCall(...args),
  runWorkflowMc: (...args: unknown[]) => unexpectedCall(...args),
  runWorkflowMcCurrent: (...args: unknown[]) => unexpectedCall(...args),
  runWorkflowValidation: (...args: unknown[]) => unexpectedCall(...args),
  runWorkflowValidationCurrent: (...args: unknown[]) => unexpectedCall(...args),
  runSelectedDes: (...args: unknown[]) => unexpectedCall(...args),
  runSelectedMc: (...args: unknown[]) => unexpectedCall(...args),
  runSelectedValidation: (...args: unknown[]) => unexpectedCall(...args),
  runSelectedDecision: (...args: unknown[]) => unexpectedCall(...args),
  createWorkflowDecision: (...args: unknown[]) => unexpectedCall(...args),
  selectWorkflowScenario: (...args: unknown[]) => unexpectedCall(...args),
  getSeparateComparison: (...args: unknown[]) => unexpectedCall(...args),
  getObservedWait: (...args: unknown[]) => unexpectedCall(...args),
}))

vi.mock('../api/optimization', () => ({
  optimize: (...args: unknown[]) => unexpectedCall(...args),
  optimizeBatch: (...args: unknown[]) => unexpectedCall(...args),
  optimizeSeparate: (...args: unknown[]) => unexpectedCall(...args),
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

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getAnalysisCurrentMock(...args),
  listAnalysisDatasets: (...args: unknown[]) => listAnalysisDatasetsMock(...args),
  patchAnalysis: (...args: unknown[]) => patchAnalysisMock(...args),
  uploadAnalysisDataset: (...args: unknown[]) => unexpectedCall(...args),
  previewAnalysisDataset: (...args: unknown[]) => unexpectedCall(...args),
  downloadSetupWorkbook: (...args: unknown[]) => unexpectedCall(...args),
}))

vi.mock('../api/scenarios', () => ({
  listScenarios: vi.fn(async () => ({ scenarios: [] })),
  createScenario: (...args: unknown[]) => unexpectedCall(...args),
}))

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getDataset: (...args: unknown[]) => unexpectedCall(...args),
  deleteDataset: (...args: unknown[]) => unexpectedCall(...args),
  uploadDataset: (...args: unknown[]) => unexpectedCall(...args),
}))

vi.mock('../api/templates', () => ({
  getTemplateGuide: vi.fn(async () => ({ structure: 'separate_queues', schema: 'events', columns: [], example_rows: [], field_guide: [], accepted_aliases: {} })),
  downloadTemplate: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const desRow = {
  time: '07:00-08:00', queue_id: 'queue_1', lambda: 4, mu: 4, c: 1, rho_sim: 0.63, Lq_sim: 0.7, Wq_sim: 0.02,
  max_queue: 7, served: 600, dropped: 0, status: 'Normal', error: null, simulation_supported: true,
}

const separateTrace = {
  results: [desRow],
  trace: [
    { t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_id: 'queue_1', queue_len_after: 1 },
    { t: 0.2, type: 'service_start', segment_id: 's1', customer_id: 1, server_id: 'server:queue_1', queue_id: 'queue_1', queue_len_after: 0 },
    { t: 0.4, type: 'service_end', segment_id: 's1', customer_id: 1, server_id: 'server:queue_1', queue_id: 'queue_1', queue_len_after: 0 },
  ],
  trace_hours: 24,
  total_hours: 24,
  event_count: 3,
  truncated: false,
  abandonment_supported: false,
  segments: [{
    segment_id: 's1', time: '07:00-08:00', lambda: 4, mu: 4, c: 1, selected_model: 'Parallel M/G/1',
    simulation_supported: true, error: null, queue_structure: 'separate', initial_queue_depth: 0, final_queue_depth: 0,
  }],
  provenance: 'CURRENT',
}

const mcRow = {
  time: '07:00-08:00', queue_id: 'queue_1', lambda: 4, mu: 4, c: 1, rho_mean: 0.63, rho_std: 0.04, rho_p95: 0.7,
  Lq_mean: 0.8, Wq_mean: 0.02, failure_rate: 0.01, failure_count: 20, status: 'PASS', error: null, ci_Wq_hw: 0.01,
  ci_Lq_hw: 0.02, adequate_samples: true, failure_rate_ci_lower: 0.007, failure_rate_ci_upper: 0.015,
  failure_rate_precision: 'high', failure_rate_adequate: true,
}

const decisionHeadline = 'Insufficient evidence to make a management recommendation.'

const summary = (wait: number, queue: number, served: number) => ({
  mean_wait_minutes: wait, max_queue: queue, admitted: served, served, customer_conservation: true,
})

const breakProposal = {
  status: 'improved',
  target_rho: 0.85,
  max_shift_minutes: 120,
  all_below_target: true,
  current_breaks: [{ queue_id: 'queue_1', label: 'Break 1', scheduled_start_time: '10:00:00', duration_minutes: 30 }],
  proposed_breaks: [
    { queue_id: 'queue_1', label: 'Break 1', scheduled_start_time: '11:00:00', duration_minutes: 30, current_start_time: '10:00:00', shift_minutes: 60 },
  ],
  moves: [{ queue_id: 'queue_1', label: 'Break 1', from: '10:00', to: '11:00', duration_minutes: 30 }],
  slots: [{ start: '10:00', end: '10:15', lambda: 4, mu: 5, working_before: 0, working_after: 1, rho_before: null, rho_after: 0.8 }],
  peak_rho: { before: null, after: 0.8 },
  slots_above_target: { before: 2, after: 0 },
  staffing_gaps: [],
  des: {
    seeds: [42, 43],
    current: { summary: summary(3.25, 4, 50), replications: [], periods: [] },
    proposed: { summary: summary(1.5, 2, 50), replications: [], periods: [] },
    comparison: { mean_wait_change_minutes: -1.75, proposed_better_runs: 2, runs: 2 },
  },
  notes: [],
  setup_hash: 'hash-1',
  dataset_id: 11,
}

function job(id: number, kind: string, result: unknown, params: Record<string, unknown>) {
  return {
    id, kind, status: 'completed', params: { analysis_id: 7, ...params }, result,
    created_at: '2026-09-13T00:00:00Z', finished_at: '2026-09-13T00:01:00Z',
  }
}

function queueSetup(structure: 'separate_queues' | 'shared_queue') {
  return {
    queue_structure: structure, fixed_server_count: structure === 'shared_queue' ? 2 : null,
    staffing_varies_by_period: false, capacity_mode: 'unlimited', total_system_capacity: null,
    abandonment_mode: 'not_modeled', patience_rate_per_hour: null, segments: [],
    separate_queue_closure_policy: 'drain_existing', queue_ids: structure === 'separate_queues' ? ['queue_1'] : [],
    breaks: structure === 'separate_queues'
      ? [{ queue_id: 'queue_1', scheduled_start_time: '10:00:00', duration_minutes: 30 }]
      : [],
  }
}

// The backend as tests/test_d7_current_evidence_dataset.py (test_8), tests/test_workflow_api.py and
// tests/test_break_apply_api.py pin it: a stored job is served only while the Setup it recorded is
// the current Setup. A shared (schema-1) selection stays selected when the queue structure does not
// change, but its Decision is withheld and reported stale.
const server = {
  structure: 'separate_queues' as 'separate_queues' | 'shared_queue',
  setup: queueSetup('separate_queues') as Record<string, unknown>,
  setupVersion: 1, // bumped whenever a request changes the stored Setup
  evidenceSetup: 1, // the Setup version the stored runs were computed for
}

function changeSetup(next: Record<string, unknown>) {
  if (JSON.stringify(next) !== JSON.stringify(server.setup)) server.setupVersion += 1
  server.setup = next
}

function serverWorkflow() {
  const evidenceIsCurrent = server.setupVersion === server.evidenceSetup
  const empty = {
    analysis_id: 7, selection: null, scenario: null, des: null, mc: null, validation: null, des_current: null,
    mc_current: null, validation_current: null, decision: null, decision_stale: false,
  }
  if (server.structure === 'separate_queues') {
    if (!evidenceIsCurrent) return empty
    return {
      ...empty,
      des_current: job(21, 'workflow_des_current', separateTrace, { scenario_id: null, dataset_id: 11 }),
      mc_current: job(22, 'workflow_mc_current', { results: [mcRow] }, { scenario_id: null, dataset_id: 11 }),
      validation_current: job(23, 'workflow_validation_current', {
        results: [{ time: '07:00-08:00', queue_id: 'queue_1', mc_failure_rate: 0.01, mc_failure_rate_adequate: true, failure_rate_cap: 0.05, validation_verdict: 'pass' }],
        verdict: { status: 'pass', failed: [], inadequate: [], total: 1 },
      }, { scenario_id: null, dataset_id: 11 }),
    }
  }
  const selection = job(1, 'workflow_selection', { scenario_id: 3 }, { scenario_id: 3 })
  const scenario = { id: 3, name: 'Plan A', dataset_id: 11, provenance: 'verified_snapshot', settings: {} }
  if (!evidenceIsCurrent) return { ...empty, selection, scenario, decision_stale: true }
  return {
    ...empty,
    selection,
    scenario,
    decision: job(30, 'workflow_decision', {
      status: 'insufficient_evidence',
      headline: decisionHeadline,
      recommendation: 'Complete the missing workflow evidence before making an adoption decision.',
      rationale: ['Missing: a completed Scenario Validation run.'],
      missing_evidence: ['a completed Scenario Validation run'],
      scenario_id: 3,
      scenario_name: 'Plan A',
      dataset_id: 11,
      evidence_ids: { selection: 1, des: 2, mc: null, validation: null },
      provenance_warning: 'Analytical estimates and simulated results are decision support.',
    }, { scenario_id: 3 }),
  }
}

function datasetRow(id: number) {
  return {
    id, analysis_id: 7, name: `Week ${id}`, source_filename: `week-${id}.csv`, source_format: 'csv', row_count: 1,
    validation: { ok: true, message: 'Input data is valid.' }, created_at: '2026-09-13T00:00:00Z', normalized: null,
  }
}

let workflowGate: Promise<void> | null = null

// Holds every workflow request until the returned function is called.
function holdWorkflowRequests(): () => void {
  let release: () => void = () => {}
  workflowGate = new Promise<void>((resolve) => { release = resolve })
  return () => {
    workflowGate = null
    release()
  }
}

// Records which of `texts` are ever inserted into the page, including text a later render removes.
function watchForText(texts: string[]) {
  const seen = new Set<string>()
  const check = (node: Node) => {
    const content = node.textContent ?? ''
    for (const text of texts) if (content.includes(text)) seen.add(text)
  }
  const handle = (records: MutationRecord[]) => {
    for (const record of records) {
      if (record.type === 'characterData') check(record.target)
      record.addedNodes.forEach(check)
    }
  }
  check(document.body)
  const observer = new MutationObserver(handle)
  observer.observe(document.body, { childList: true, subtree: true, characterData: true })
  return {
    seen: () => {
      handle(observer.takeRecords())
      return [...seen]
    },
    stop: () => {
      handle(observer.takeRecords())
      observer.disconnect()
      return [...seen]
    },
  }
}

// Text that only a stored Current run can put on the Simulate page.
const CURRENT_EVIDENCE_TEXT = [
  'CURRENT configuration',
  'Discrete-event simulation results by interval',
  'Monte Carlo simulation results by interval',
  'Simulation validation passed.',
]

function Nav() {
  return (
    <nav>
      <Link to="/analyses/7/setup">Open Setup</Link>
      <Link to="/analyses/7/optimize">Open Optimize</Link>
      <Link to="/analyses/7/simulate">Open Simulate</Link>
      <Link to="/analyses/7/decision">Open Decision</Link>
    </nav>
  )
}

function renderApp(route: string) {
  // The application's cache defaults (30 s staleTime), not the test default: the defect lives in
  // the window where cached workflow evidence is still considered fresh.
  const queryClient = new QueryClient({ defaultOptions: appQueryClient.getDefaultOptions() })
  return renderWithProviders(
    <>
      <Nav />
      <Routes>
        <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
        <Route path="/analyses/:analysisId/optimize" element={<OptimizePage />} />
        <Route path="/analyses/:analysisId/simulate" element={<SimulationPage />} />
        <Route path="/analyses/:analysisId/decision" element={<DecisionEndpointPage />} />
      </Routes>
    </>,
    { route, queryClient },
  )
}

async function saveServerCountOnSetup(user: ReturnType<typeof userEvent.setup>, value: string) {
  const versionBefore = server.setupVersion
  await user.click(screen.getByRole('link', { name: 'Open Setup' }))
  fireEvent.change(await screen.findByLabelText('Fixed server count'), { target: { value } })
  await user.click(screen.getByRole('button', { name: 'Save' }))
  expect(await screen.findByText('Queue setup saved.')).toBeInTheDocument()
  expect(server.setupVersion).toBe(versionBefore + 1)
}

async function applyBreaksOnOptimize(user: ReturnType<typeof userEvent.setup>) {
  const versionBefore = server.setupVersion
  await user.click(screen.getByRole('link', { name: 'Open Optimize' }))
  await user.click(await screen.findByRole('button', { name: 'Suggest break times' }))
  await user.click(await screen.findByRole('button', { name: 'Apply to Setup' }))
  expect(await screen.findByText('Setup updated with the proposed breaks. Rerun the workflow from Current.')).toBeInTheDocument()
  expect(server.setupVersion).toBe(versionBefore + 1)
}

beforeEach(() => {
  server.structure = 'separate_queues'
  server.setup = queueSetup('separate_queues')
  server.setupVersion = 1
  server.evidenceSetup = 1
  workflowGate = null
  getWorkflowMock.mockReset().mockImplementation(async () => {
    if (workflowGate) await workflowGate
    return serverWorkflow()
  })
  getAnalysisMock.mockReset().mockImplementation(async () => ({
    analysis: { id: 7, name: 'Checkout', queue_setup: structuredClone(server.setup) },
  }))
  patchAnalysisMock.mockReset().mockImplementation(async (_id: number, payload: { queue_setup: Record<string, unknown> }) => {
    changeSetup(structuredClone(payload.queue_setup))
    return { analysis: { id: 7, name: 'Checkout', queue_setup: structuredClone(server.setup) } }
  })
  getAnalysisCurrentMock.mockReset().mockImplementation(async () => ({
    dataset: { id: 11, analysis_id: 7, name: 'Week 11' }, rows: [], kpis: {}, explanations: [], selected_model: 'Parallel M/G/1',
  }))
  listAnalysisDatasetsMock.mockReset().mockImplementation(async () => ({ datasets: [datasetRow(11)] }))
  listDatasetsMock.mockReset().mockImplementation(async () => ({ datasets: [datasetRow(11)] }))
  optimizeSeparateBreaksMock.mockReset().mockResolvedValue(breakProposal)
  // The server writes only the proposed break start times into the Setup (tests/test_break_apply_api.py).
  applySeparateBreaksMock.mockReset().mockImplementation(async () => {
    changeSetup({
      ...server.setup,
      breaks: [{ queue_id: 'queue_1', scheduled_start_time: '11:00:00', duration_minutes: 30, original_start_time: '10:00:00' }],
    })
    return { analysis: { id: 7, name: 'Checkout', queue_setup: structuredClone(server.setup) }, moves_applied: 1 }
  })
  unexpectedCall.mockReset()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Setup changes and cached workflow evidence', () => {
  it('never shows the previous Setup\'s Current runs on Simulate after a Setup save', async () => {
    const user = userEvent.setup()
    renderApp('/analyses/7/simulate')
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()
    expect(screen.getByText('Simulation validation passed.')).toBeInTheDocument()

    await saveServerCountOnSetup(user, '2')
    const release = holdWorkflowRequests()
    const watch = watchForText(CURRENT_EVIDENCE_TEXT)
    const requestsBefore = getWorkflowMock.mock.calls.length
    await user.click(screen.getByRole('link', { name: 'Open Simulate' }))
    expect(watch.seen()).toEqual([])
    await waitFor(() => expect(getWorkflowMock.mock.calls.length).toBeGreaterThan(requestsBefore))
    expect(watch.seen()).toEqual([])

    release()
    expect(await screen.findByText('No current run for dataset #11.')).toBeInTheDocument()
    expect(watch.stop()).toEqual([])
    expect(unexpectedCall).not.toHaveBeenCalled()
  })

  it('never shows the previous Setup\'s Decision after a Setup save', async () => {
    server.structure = 'shared_queue'
    server.setup = queueSetup('shared_queue')
    const user = userEvent.setup()
    renderApp('/analyses/7/decision')
    expect(await screen.findByText(decisionHeadline)).toBeInTheDocument()

    await saveServerCountOnSetup(user, '3')
    const release = holdWorkflowRequests()
    const watch = watchForText([decisionHeadline])
    const requestsBefore = getWorkflowMock.mock.calls.length
    await user.click(screen.getByRole('link', { name: 'Open Decision' }))
    expect(watch.seen()).toEqual([])
    await waitFor(() => expect(getWorkflowMock.mock.calls.length).toBeGreaterThan(requestsBefore))
    expect(watch.seen()).toEqual([])

    release()
    expect(await screen.findByText('No current Decision')).toBeInTheDocument()
    expect(watch.stop()).toEqual([])
  })

  it('never flashes the previous Setup\'s Current runs on Simulate while the workflow refetches after a break apply', async () => {
    const user = userEvent.setup()
    renderApp('/analyses/7/simulate')
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()

    await applyBreaksOnOptimize(user)
    const release = holdWorkflowRequests()
    const watch = watchForText(CURRENT_EVIDENCE_TEXT)
    const requestsBefore = getWorkflowMock.mock.calls.length
    await user.click(screen.getByRole('link', { name: 'Open Simulate' }))
    expect(watch.seen()).toEqual([])
    await waitFor(() => expect(getWorkflowMock.mock.calls.length).toBeGreaterThan(requestsBefore))
    expect(watch.seen()).toEqual([])

    release()
    expect(await screen.findByText('No current run for dataset #11.')).toBeInTheDocument()
    expect(watch.stop()).toEqual([])
    expect(unexpectedCall).not.toHaveBeenCalled()
  })
})
