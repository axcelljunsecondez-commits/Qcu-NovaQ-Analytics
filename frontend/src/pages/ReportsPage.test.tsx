import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { ReportsPage } from './ReportsPage'

const listDatasetsMock = vi.fn()
const listScenariosMock = vi.fn()
const fetchReportMock = vi.fn()
const fetchSelectedReportMock = vi.fn()
const fetchSelectedPreviewMock = vi.fn()
const getWorkflowMock = vi.fn()
const getAnalysisMock = vi.fn()
const createObjectURLMock = vi.fn()
const revokeObjectURLMock = vi.fn()
let clickSpy: ReturnType<typeof vi.spyOn>

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getDataset: vi.fn(),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: vi.fn(),
}))

vi.mock('../api/reports', async () => {
  const actual = await vi.importActual<typeof import('../api/reports')>('../api/reports')
  return {
    ...actual,
    fetchReport: (...args: unknown[]) => fetchReportMock(...args),
    fetchSelectedReport: (...args: unknown[]) => fetchSelectedReportMock(...args),
    fetchSelectedPreview: (...args: unknown[]) => fetchSelectedPreviewMock(...args),
  }
})

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
}))

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
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

const scenario = {
  id: 1,
  dataset_id: 1,
  name: 'Plan A',
  settings: {},
  results: { results: [] },
  created_at: '2026-08-02T10:00:00Z',
}

const decision = {
  status: 'adopt',
  headline: 'Adopt Scenario "Plan A".',
  recommendation: 'All intervals passed and modeled cost decreases.',
  rationale: ['Selected Scenario: Plan A (ID 1).'],
  missing_evidence: [],
  scenario_id: 1,
  scenario_name: 'Plan A',
  dataset_id: 1,
  evidence_ids: { selection: 2, des: 3, mc: null, validation: 4 },
  provenance_warning: 'Simulation is decision support, not an observed future outcome.',
}

function workflow(decisionResult: typeof decision | null) {
  return {
    analysis_id: 7,
    selection: null,
    scenario: { id: 1, name: 'Plan A', dataset_id: 1, provenance: 'verified_snapshot' },
    des: null,
    mc: null,
    validation: null,
    decision: decisionResult ? {
      id: 5,
      kind: 'workflow_decision',
      status: 'completed',
      params: {},
      result: decisionResult,
      created_at: '2026-09-13T00:00:00Z',
      finished_at: '2026-09-13T00:01:00Z',
    } : null,
    decision_stale: false,
  }
}

function renderAnalysisReports() {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId/reports" element={<ReportsPage />} />
    </Routes>,
    { route: '/analyses/7/reports' },
  )
}

beforeEach(() => {
  listDatasetsMock.mockReset()
  listScenariosMock.mockReset()
  fetchReportMock.mockReset()
  getWorkflowMock.mockReset().mockResolvedValue(workflow(decision))
  listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
  listScenariosMock.mockResolvedValue({ scenarios: [scenario] })
  fetchReportMock.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }))
  fetchSelectedReportMock.mockReset().mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }))
  fetchSelectedPreviewMock.mockReset()
  getAnalysisMock.mockReset().mockResolvedValue({
    analysis: { id: 7, queue_setup: { queue_structure: 'shared_queue', queue_ids: [] } },
  })
  createObjectURLMock.mockReset().mockReturnValue('blob:report')
  revokeObjectURLMock.mockReset()
  clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: createObjectURLMock,
    revokeObjectURL: revokeObjectURLMock,
  })
})

afterEach(() => {
  clickSpy.mockRestore()
  vi.unstubAllGlobals()
})

describe('ReportsPage', () => {
  it('previews only the sections and sheets produced by the current exporters', async () => {
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const preview = await screen.findByTestId('report-preview')
    const pdf = within(preview).getByRole('region', { name: 'PDF sections' })
    const excel = within(preview).getByRole('region', { name: 'Excel sheets' })

    expect(within(pdf).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'QCU Queue Analysis Report',
      'Executive Summary',
      'Segment Comparison',
      'Recommendations',
    ])
    expect(within(excel).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Summary',
      'Segments',
      'Recommendations — Included when recommendation evidence is available.',
    ])
    expect(within(preview).queryByText(/Simulation Validation|ROI|Methodology|Appendix/i)).not.toBeInTheDocument()
  })

  it('shows dataset and scenario source cards with PDF/Excel buttons', async () => {
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const datasetCard = await screen.findByTestId('report-card-datasets')
    const scenarioCard = await screen.findByTestId('report-card-scenarios')
    expect(await within(datasetCard).findByRole('option', { name: 'sample' })).toBeInTheDocument()
    expect(within(scenarioCard).getByRole('option', { name: 'Plan A' })).toBeInTheDocument()
    expect(within(datasetCard).getByRole('button', { name: 'Download PDF' })).toBeInTheDocument()
    expect(within(datasetCard).getByRole('button', { name: 'Download Excel' })).toBeInTheDocument()
    expect(within(scenarioCard).getByRole('button', { name: 'Download PDF' })).toBeInTheDocument()
    expect(within(scenarioCard).getByRole('button', { name: 'Download Excel' })).toBeInTheDocument()
  })

  it('downloads a dataset PDF as a blob and triggers the anchor download', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const datasetCard = await screen.findByTestId('report-card-datasets')
    await within(datasetCard).findByRole('option', { name: 'sample' })
    await user.click(within(datasetCard).getByRole('button', { name: 'Download PDF' }))
    await waitFor(() => {
      expect(fetchReportMock).toHaveBeenCalledWith('datasets', 1, 'pdf')
    })
    await waitFor(() => {
      expect(createObjectURLMock).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(revokeObjectURLMock).toHaveBeenCalled()
    })
    expect(await screen.findByText('Report downloaded.')).toBeInTheDocument()
  })

  it('downloads a scenario Excel via the scenario source card', async () => {
    const user = userEvent.setup()
    const downloadSpy = vi.spyOn(HTMLAnchorElement.prototype, 'download', 'set')
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const scenarioCard = await screen.findByTestId('report-card-scenarios')
    await within(scenarioCard).findByRole('option', { name: 'Plan A' })
    await user.click(within(scenarioCard).getByRole('button', { name: 'Download Excel' }))
    await waitFor(() => {
      expect(fetchReportMock).toHaveBeenCalledWith('scenarios', 1, 'excel')
    })
    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith('novaq_scenarios_1.xlsx')
    })
    downloadSpy.mockRestore()
  })

  it('shows the empty state when no datasets or scenarios exist', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [] })
    listScenariosMock.mockResolvedValue({ scenarios: [] })
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    expect(await screen.findByText('No data available for reports.')).toBeInTheDocument()
  })

  it('blocks an analysis scenario report until a matching Decision exists', async () => {
    getWorkflowMock.mockResolvedValue(workflow(null))
    renderAnalysisReports()
    expect(await screen.findByText(/Generate a Decision before exporting/)).toBeInTheDocument()
    const card = await screen.findByTestId('report-card-scenarios')
    expect(within(card).getByRole('button', { name: 'Download PDF' })).toBeDisabled()
    expect(within(card).getByRole('button', { name: 'Download Excel' })).toBeDisabled()
  })

  it('does not present or export a stale Decision as current', async () => {
    getWorkflowMock.mockResolvedValue({ ...workflow(decision), decision_stale: true })
    renderAnalysisReports()
    expect(await screen.findByText(/Decision is stale/)).toBeInTheDocument()
    expect(screen.queryByTestId('report-decision')).not.toBeInTheDocument()
    const card = await screen.findByTestId('report-card-scenarios')
    expect(within(card).getByRole('button', { name: 'Download PDF' })).toBeDisabled()
    expect(within(card).getByRole('button', { name: 'Download Excel' })).toBeDisabled()
  })

  it('shows and exports the persisted Decision recommendation', async () => {
    const user = userEvent.setup()
    renderAnalysisReports()
    const summary = await screen.findByTestId('report-decision')
    expect(within(summary).getByText('Adopt Scenario "Plan A".')).toBeInTheDocument()
    const card = await screen.findByTestId('report-card-scenarios')
    await user.click(within(card).getByRole('button', { name: 'Download PDF' }))
    await waitFor(() => expect(fetchReportMock).toHaveBeenCalledWith('scenarios', 1, 'pdf', 7))
  })
})

describe('separate full report', () => {
  function renderSeparateReports() {
    getAnalysisMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues', queue_ids: ['east-07', 'lane-A'] } },
    })
    return renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/reports" element={<ReportsPage />} />
      </Routes>,
      { route: '/analyses/7/reports' },
    )
  }

  const previewModel = {
    overview: {
      analysis_id: 7, analysis_name: 'East lanes', queue_structure: 'separate_queues',
      dataset_id: 2, dataset_name: 'lanes.csv', scenario_id: 9,
      scenario_name: 'Optimal @ 70%', target: 0.7, decision: 'conditional',
      generated_at: '2026-09-18T00:00:00+00:00',
    },
    dataset: { row_count: 2, periods: ['08:00'], queue_ids: ['east-07', 'lane-A'], queue_count: 2 },
    queue_config: { model: 'one queue_id = one physical queue + one physical single server' },
    current: {
      periods: [{
        time: '08:00',
        queues: [
          { queue_id: 'east-07', lambda: 4.0, rho: 0.36, Wq: 0.05, model: 'M/G/1', stable: true },
          { queue_id: 'lane-A', lambda: 2.0, rho: 0.18, Wq: 0.02, model: 'M/G/1', stable: true },
        ],
      }],
      wait_mean: 0.04, peak_utilization: 0.36, waiting_cost: 25.0,
    },
    optimization: { evaluation_method: 'DES_REPLICATIONS', target: 0.7 },
    comparison_plans: [{ scenario_id: 9, name: 'Optimal @ 70%', target: 0.7, overall: 'COMPLETE' }],
    selected: { scenario_id: 9, name: 'Optimal @ 70%' },
    schedule: {
      periods: [{
        time: '08:00', current_active_lanes: ['east-07', 'lane-A'],
        optimal_active_lanes: 1, adjustment: -1, peak_utilization: 0.55,
        optimum: { active_queue_ids: ['east-07'], inactive_queue_ids: ['lane-A'] },
      }],
    },
    des: { overall_conservation: true, overall_status: 'COMPLETED', periods: [] },
    mc: { lanes: [] },
    validation: { verdict: 'pass', periods: [] },
    decision: {
      status: 'conditional',
      headline: 'Consider Scenario "Optimal @ 70%" conditionally.',
      recommendation: 'All 1 validation checks passed, but modeled savings are unavailable.',
      rationale: ['Selected Scenario: Optimal @ 70% (ID 9).'],
      facts: { lane_delta: -1 },
      failed_periods: [],
    },
    staffing_title: 'Selected Staffing Schedule',
    cost: {
      current_waiting: 25.0, selected_total: 180.0,
      current_total: null, savings: null, roi: null,
    },
    limitations: ['Each optimized period was simulated independently (period-independent execution).'],
    provenance: { scenario_id: 9, des_job_id: 10, decision_job_id: 13 },
  }

  it('renders context, preview sections, and the selected schedule', async () => {
    fetchSelectedPreviewMock.mockResolvedValue({ model: previewModel })
    renderSeparateReports()
    expect(await screen.findByText('Optimal @ 70%')).toBeInTheDocument()
    expect(screen.getByText('Decision: CONDITIONAL')).toBeInTheDocument()
    expect(screen.getByRole('rowheader', { name: '08:00' })).toBeInTheDocument()
    expect(screen.getAllByText(/east-07/).length).toBeGreaterThan(0)
    expect(fetchReportMock).not.toHaveBeenCalled()
  })

  it('blocks export with the exact missing stage and keeps buttons disabled', async () => {
    fetchSelectedPreviewMock.mockRejectedValue({
      response: { data: { detail: 'Run selected-plan Decision before generating the final report.' } },
    })
    renderSeparateReports()
    expect(await screen.findByText(/Run selected-plan Decision/)).toBeInTheDocument()
    const card = await screen.findByTestId('report-card-separate')
    expect(within(card).getByRole('button', { name: 'Download PDF' })).toBeDisabled()
    expect(within(card).getByRole('button', { name: 'Download Excel' })).toBeDisabled()
  })

  it('exports PDF and Excel from the previewed chain without shared endpoints', async () => {
    const user = userEvent.setup()
    fetchSelectedPreviewMock.mockResolvedValue({ model: previewModel })
    renderSeparateReports()
    const card = await screen.findByTestId('report-card-separate')
    await user.click(within(card).getByRole('button', { name: 'Download PDF' }))
    await waitFor(() => expect(fetchSelectedReportMock).toHaveBeenCalledWith(7, 'pdf'))
    await user.click(within(card).getByRole('button', { name: 'Download Excel' }))
    await waitFor(() => expect(fetchSelectedReportMock).toHaveBeenCalledWith(7, 'excel'))
    expect(fetchReportMock).not.toHaveBeenCalled()
  })

  it('shows N/A costs without fabricating savings or ROI', async () => {
    fetchSelectedPreviewMock.mockResolvedValue({ model: previewModel })
    renderSeparateReports()
    await screen.findByTestId('report-card-separate')
    expect(screen.getAllByText('N/A').length).toBeGreaterThan(0)
    expect(screen.queryByText(/Savings: ₱/)).not.toBeInTheDocument()
    expect(screen.queryByText(/ROI: [0-9]/)).not.toBeInTheDocument()
  })
})
