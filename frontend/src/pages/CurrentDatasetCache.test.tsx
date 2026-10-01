import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Link, Route, Routes } from 'react-router-dom'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient } from '@tanstack/react-query'
import { renderWithProviders } from '../test/test-utils'
import { queryClient as appQueryClient } from '../lib/queryClient'
import { AnalysisSetupPage } from './AnalysisSetupPage'
import { DatasetsPage } from './DatasetsPage'
import { SimulationPage } from './SimulationPage'
import { DecisionEndpointPage } from '../components/analysis/DecisionEndpointPage'
import { ComparisonPage } from './ComparisonPage'

// A dataset upload or deletion can change which dataset is current for an analysis. The workflow
// evidence cached for the replaced dataset must never be shown again, not even while the fresh
// workflow request is in flight.

const getWorkflowMock = vi.fn()
const getAnalysisMock = vi.fn()
const getAnalysisCurrentMock = vi.fn()
const listAnalysisDatasetsMock = vi.fn()
const uploadAnalysisDatasetMock = vi.fn()
const listDatasetsMock = vi.fn()
const deleteDatasetMock = vi.fn()
const listScenariosMock = vi.fn()
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
}))

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getAnalysisCurrentMock(...args),
  listAnalysisDatasets: (...args: unknown[]) => listAnalysisDatasetsMock(...args),
  uploadAnalysisDataset: (...args: unknown[]) => uploadAnalysisDatasetMock(...args),
  previewAnalysisDataset: (...args: unknown[]) => unexpectedCall(...args),
  patchAnalysis: (...args: unknown[]) => unexpectedCall(...args),
  downloadSetupWorkbook: (...args: unknown[]) => unexpectedCall(...args),
}))

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: (...args: unknown[]) => unexpectedCall(...args),
}))

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  deleteDataset: (...args: unknown[]) => deleteDatasetMock(...args),
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
    breaks: [],
  }
}

// The backend as the D7 suite pins it (tests/test_d7_current_evidence_dataset.py): the current
// dataset is the highest valid id, and evidence is served only while its dataset is current.
const server = {
  structure: 'separate_queues' as 'separate_queues' | 'shared_queue',
  datasets: [] as number[], // highest id first; every one successfully processed
  evidenceFor: null as number | null, // the dataset the latest stored runs were computed on
}

function currentDatasetId(): number | null {
  return server.datasets[0] ?? null
}

function serverWorkflow() {
  const current = currentDatasetId()
  const evidenceIsCurrent = current !== null && current === server.evidenceFor
  const empty = {
    analysis_id: 7, des: null, mc: null, validation: null, des_current: null, mc_current: null,
    validation_current: null, decision: null, decision_stale: false,
  }
  if (server.structure === 'separate_queues') {
    if (!evidenceIsCurrent) return { ...empty, selection: null, scenario: null }
    return {
      ...empty,
      selection: null,
      scenario: null,
      des_current: job(21, 'workflow_des_current', separateTrace, { scenario_id: null, dataset_id: current }),
      mc_current: job(22, 'workflow_mc_current', { results: [mcRow] }, { scenario_id: null, dataset_id: current }),
      validation_current: job(23, 'workflow_validation_current', {
        results: [{ time: '07:00-08:00', queue_id: 'queue_1', mc_failure_rate: 0.01, mc_failure_rate_adequate: true, failure_rate_cap: 0.05, validation_verdict: 'pass' }],
        verdict: { status: 'pass', failed: [], inadequate: [], total: 1 },
      }, { scenario_id: null, dataset_id: current }),
    }
  }
  // A shared-queue selection survives a dataset change; its scenario and Decision do not.
  const selection = job(1, 'workflow_selection', { scenario_id: 3 }, { scenario_id: 3 })
  if (!evidenceIsCurrent) return { ...empty, selection, scenario: null }
  return {
    ...empty,
    selection,
    scenario: { id: 3, name: 'Plan A', dataset_id: current, provenance: 'verified_snapshot', settings: {} },
    decision: job(30, 'workflow_decision', {
      status: 'insufficient_evidence',
      headline: decisionHeadline,
      recommendation: 'Complete the missing workflow evidence before making an adoption decision.',
      rationale: ['Missing: a completed Scenario Validation run.'],
      missing_evidence: ['a completed Scenario Validation run'],
      scenario_id: 3,
      scenario_name: 'Plan A',
      dataset_id: current,
      evidence_ids: { selection: 1, des: 2, mc: null, validation: null },
      provenance_warning: 'Analytical estimates and simulated results are decision support.',
    }, { scenario_id: 3 }),
  }
}

const planRow = {
  time: '08:00-09:00', lambda_: 30, mu: 12, c_current: 3, c_optimal: 4, rho_current: 0.9, rho_optimal: 0.7,
  Wq_current: 0.1, Wq_optimal: 0.05, Lq_current: 3.5, Lq_optimal: 0.5, cost_current: 800, cost_optimal: 500,
  delta_cost: 300, delta_Wq: 0.05, delta_Lq: 3, delta_c: 1, delta_rho: -0.2, waiting_cost_current: 300,
  waiting_cost_optimal: 150, abandonment_cost_current: 100, abandonment_cost_optimal: 50, cost_per_server: 87,
  current_stable: true, optimized_stable: true, recommendation: '', warning: '',
}

// GET /scenarios as the 4c backend serves it: the saved plan is CURRENT only on its own dataset.
function serverScenarios() {
  const current = currentDatasetId() === server.evidenceFor
  return [{
    id: 3, analysis_id: 7, dataset_id: server.evidenceFor, name: 'Plan A', settings: {},
    results: { results: [planRow] }, created_at: '2026-09-13T00:00:00Z',
    evidence_status: current ? 'CURRENT' : 'STALE_DATASET',
    evidence_reasons: current ? [] : [{ code: 'DATASET_NOT_CURRENT', subject: 'scenario 3', detail: 'Scenario is stale for the current dataset.' }],
  }]
}

function datasetRow(id: number) {
  return {
    id, analysis_id: 7, name: `Week ${id}`, source_filename: `week-${id}.csv`, source_format: 'csv', row_count: 1,
    validation: { ok: true, message: 'Input data is valid.' }, created_at: '2026-09-13T00:00:00Z', normalized: null,
  }
}

let workflowGate: Promise<void> | null = null
let scenariosGate: Promise<void> | null = null

// Holds every scenario-list request until the returned function is called.
function holdScenarioRequests(): () => void {
  let release: () => void = () => {}
  scenariosGate = new Promise<void>((resolve) => { release = resolve })
  return () => {
    scenariosGate = null
    release()
  }
}

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
      <Link to="/analyses/7/simulate">Open Simulate</Link>
      <Link to="/analyses/7/decision">Open Decision</Link>
      <Link to="/datasets">Open Datasets</Link>
      <Link to="/analyses/7/compare">Open Compare</Link>
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
        <Route path="/analyses/:analysisId/simulate" element={<SimulationPage />} />
        <Route path="/analyses/:analysisId/decision" element={<DecisionEndpointPage />} />
        <Route path="/datasets" element={<DatasetsPage />} />
        <Route path="/analyses/:analysisId/compare" element={<ComparisonPage />} />
      </Routes>
    </>,
    { route, queryClient },
  )
}

async function uploadOnSetup(user: ReturnType<typeof userEvent.setup>, expectedId: number) {
  await user.click(screen.getByRole('link', { name: 'Open Setup' }))
  await user.upload(await screen.findByLabelText('Upload Data'), new File(['a,b\n1,2\n'], 'week.csv', { type: 'text/csv' }))
  await user.click(screen.getByRole('button', { name: 'Upload and process' }))
  expect(await screen.findByText(`Dataset ${expectedId} processed.`)).toBeInTheDocument()
}

async function deleteOnDatasets(user: ReturnType<typeof userEvent.setup>, datasetId: number) {
  await user.click(screen.getByRole('link', { name: 'Open Datasets' }))
  const row = (await screen.findByRole('rowheader', { name: `Week ${datasetId}` })).closest('tr')
  expect(row).not.toBeNull()
  await user.click(within(row as HTMLElement).getByRole('button', { name: 'Delete' }))
  await waitFor(() => expect(deleteDatasetMock).toHaveBeenCalledWith(datasetId))
  await waitFor(() => expect(screen.queryByRole('rowheader', { name: `Week ${datasetId}` })).not.toBeInTheDocument())
}

beforeEach(() => {
  server.structure = 'separate_queues'
  server.datasets = [11]
  server.evidenceFor = 11
  workflowGate = null
  getWorkflowMock.mockReset().mockImplementation(async () => {
    if (workflowGate) await workflowGate
    return serverWorkflow()
  })
  getAnalysisMock.mockReset().mockImplementation(async () => ({
    analysis: { id: 7, name: 'Checkout', queue_setup: queueSetup(server.structure) },
  }))
  getAnalysisCurrentMock.mockReset().mockImplementation(async () => {
    const id = currentDatasetId()
    if (id === null) {
      throw Object.assign(new Error('Request failed with status code 404'), {
        response: { status: 404, data: { detail: 'This Analysis has no successfully processed dataset.' } },
      })
    }
    return { dataset: { id, analysis_id: 7, name: `Week ${id}` }, rows: [], kpis: {}, explanations: [], selected_model: 'Parallel M/G/1' }
  })
  listAnalysisDatasetsMock.mockReset().mockImplementation(async () => ({ datasets: server.datasets.map(datasetRow) }))
  listDatasetsMock.mockReset().mockImplementation(async () => ({ datasets: server.datasets.map(datasetRow) }))
  scenariosGate = null
  listScenariosMock.mockReset().mockImplementation(async () => {
    if (scenariosGate) await scenariosGate
    return { scenarios: serverScenarios() }
  })
  uploadAnalysisDatasetMock.mockReset().mockImplementation(async () => {
    const id = (server.datasets[0] ?? 10) + 1
    server.datasets = [id, ...server.datasets]
    return { dataset: { ...datasetRow(id), validation: { ok: true, message: `Dataset ${id} processed.` } } }
  })
  deleteDatasetMock.mockReset().mockImplementation(async (id: number) => {
    server.datasets = server.datasets.filter((item) => item !== id)
    return { detail: 'Dataset deleted.' }
  })
  unexpectedCall.mockReset()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('Current dataset changes and cached workflow evidence', () => {
  it('never shows the replaced dataset\'s Current runs on Simulate after a Setup upload', async () => {
    const user = userEvent.setup()
    renderApp('/analyses/7/simulate')
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()
    expect(screen.getByText('Simulation validation passed.')).toBeInTheDocument()

    await uploadOnSetup(user, 12)
    const release = holdWorkflowRequests()
    const watch = watchForText(CURRENT_EVIDENCE_TEXT)
    const requestsBefore = getWorkflowMock.mock.calls.length
    await user.click(screen.getByRole('link', { name: 'Open Simulate' }))
    expect(watch.seen()).toEqual([])
    await waitFor(() => expect(getWorkflowMock.mock.calls.length).toBeGreaterThan(requestsBefore))
    expect(watch.seen()).toEqual([])

    release()
    expect(await screen.findByText('No current run for dataset #12.')).toBeInTheDocument()
    expect(watch.stop()).toEqual([])
    expect(unexpectedCall).not.toHaveBeenCalled()
  })

  it('never shows the replaced dataset\'s Decision after a Setup upload', async () => {
    server.structure = 'shared_queue'
    const user = userEvent.setup()
    renderApp('/analyses/7/decision')
    expect(await screen.findByText(decisionHeadline)).toBeInTheDocument()

    await uploadOnSetup(user, 12)
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

  it('never shows the deleted current dataset\'s Current runs, and names the dataset that is current again', async () => {
    server.datasets = [12, 11]
    server.evidenceFor = 12
    const user = userEvent.setup()
    renderApp('/analyses/7/simulate')
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()

    await deleteOnDatasets(user, 12)
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
  })

  it('shows no Current runs and no dataset number once the analysis\'s only dataset is deleted', async () => {
    server.datasets = [12]
    server.evidenceFor = 12
    const user = userEvent.setup()
    renderApp('/analyses/7/simulate')
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()

    await deleteOnDatasets(user, 12)
    const release = holdWorkflowRequests()
    const watch = watchForText([...CURRENT_EVIDENCE_TEXT, 'No current run for dataset'])
    const requestsBefore = getWorkflowMock.mock.calls.length
    const lookupsBefore = getAnalysisCurrentMock.mock.calls.length
    await user.click(screen.getByRole('link', { name: 'Open Simulate' }))
    expect(watch.seen()).toEqual([])
    await waitFor(() => expect(getWorkflowMock.mock.calls.length).toBeGreaterThan(requestsBefore))

    release()
    expect(await screen.findByRole('heading', { name: 'Simulate Current' })).toBeInTheDocument()
    await waitFor(() => expect(getAnalysisCurrentMock.mock.calls.length).toBeGreaterThan(lookupsBefore))
    await waitFor(() => expect(getAnalysisCurrentMock.mock.results.at(-1)?.type).toBe('return'))
    expect(screen.getByRole('button', { name: 'Run Current DES' })).toBeInTheDocument()
    expect(watch.stop()).toEqual([])
  })

  it('keeps showing the current dataset\'s runs when a non-current dataset is deleted', async () => {
    server.datasets = [12, 11]
    server.evidenceFor = 12
    const user = userEvent.setup()
    const { queryClient } = renderApp('/analyses/7/simulate')
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()

    await deleteOnDatasets(user, 11)
    await user.click(screen.getByRole('link', { name: 'Open Simulate' }))
    expect(await screen.findByText('CURRENT configuration')).toBeInTheDocument()
    expect(screen.getByText('Simulation validation passed.')).toBeInTheDocument()
    await waitFor(() => expect(queryClient.getQueryState(['current', 7])?.fetchStatus).toBe('idle'))
    // What the page shows is the server's evidence for dataset 12, which is still the current one.
    const workflow = queryClient.getQueryData<{ des_current: { params: { dataset_id: unknown } } | null }>(['workflow', 7])
    const current = queryClient.getQueryData<{ dataset: { id: number } }>(['current', 7])
    expect(workflow?.des_current?.params.dataset_id).toBe(12)
    expect(current?.dataset.id).toBe(12)
    expect(workflow).toEqual(serverWorkflow())
    expect(screen.queryByText(/No current run for dataset/)).not.toBeInTheDocument()
  })

  it('never shows the scenario of a replaced dataset as current on Compare after a Setup upload', async () => {
    server.structure = 'shared_queue'
    const user = userEvent.setup()
    renderApp('/analyses/7/compare')
    expect(await screen.findByTestId('compare-totals-dataset')).toHaveTextContent('Totals computed from dataset #11.')

    await uploadOnSetup(user, 12)
    const release = holdScenarioRequests()
    const watch = watchForText(['Current Total Cost', 'Totals computed from dataset'])
    const requestsBefore = listScenariosMock.mock.calls.length
    await user.click(screen.getByRole('link', { name: 'Open Compare' }))
    expect(watch.seen()).toEqual([])
    await waitFor(() => expect(listScenariosMock.mock.calls.length).toBeGreaterThan(requestsBefore))
    expect(watch.seen()).toEqual([])

    release()
    expect(await screen.findByTestId('compare-not-current')).toHaveTextContent('Stale: dataset replaced')
    expect(watch.stop()).toEqual([])
  })
})
