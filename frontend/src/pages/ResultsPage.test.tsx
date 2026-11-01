import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes, useLocation } from 'react-router-dom'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import type { DatasetOut, QueueSetup } from '../api/types'
import { ResultsPage } from './ResultsPage'
import { PlanChanges } from '../components/results/PlanChanges'

// Analysis results (spec 2026-10-09 §7.7, plan phase U6). Every value must come from the
// selected file's response; a review-only or older file never reaches plans or simulation.

const getAnalysisMock = vi.fn()
const listDatasetsMock = vi.fn()
const getCurrentMock = vi.fn()
const getObservedMock = vi.fn()
const getWorkflowMock = vi.fn()
const listScenariosMock = vi.fn()
const getSeparateMock = vi.fn()
const selectMock = vi.fn()

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  listAnalyses: vi.fn(async () => ({ analyses: [{ id: 7, name: 'Checkout', archived_at: null }] })),
  listAnalysisDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getCurrentMock(...args),
}))
vi.mock('../api/workflow', () => ({
  getObservedWait: (...args: unknown[]) => getObservedMock(...args),
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  getSeparateComparison: (...args: unknown[]) => getSeparateMock(...args),
  selectWorkflowScenario: (...args: unknown[]) => selectMock(...args),
}))
vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
}))
vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

function setup(structure: 'shared_queue' | 'separate_queues'): QueueSetup {
  return {
    queue_structure: structure, fixed_server_count: structure === 'shared_queue' ? 3 : null, staffing_varies_by_period: false,
    capacity_mode: 'unlimited', total_system_capacity: null, abandonment_mode: 'not_modeled', patience_rate_per_hour: null,
    segments: [], separate_queue_closure_policy: 'drain_existing', queue_ids: structure === 'separate_queues' ? ['A', 'B'] : [], breaks: [],
  }
}

function analysis(structure: 'shared_queue' | 'separate_queues' = 'shared_queue') {
  return { analysis: { id: 7, name: 'Checkout', service_type: null, location_label: null, queue_setup: setup(structure),
    setup_status: 'ready', archived_at: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' } }
}

const planningFile: DatasetOut = {
  id: 11, analysis_id: 7, name: 'march', source_filename: 'march_records.csv', source_format: 'csv', row_count: 3,
  validation: { ok: true, message: 'ok', derived_statistics: [{ time: '08:00-09:00' }] }, created_at: '2026-10-09T03:00:00Z',
  normalized: null, purpose: 'planning', is_current: true, data_dates: { first: '2026-03-01', last: '2026-03-31', source: 'stored_at_upload' },
}
const reviewFile: DatasetOut = {
  id: 12, analysis_id: 7, name: 'feb', source_filename: 'feb_totals.csv', source_format: 'csv', row_count: 1,
  validation: { ok: true, message: 'ok' }, created_at: '2026-10-10T03:00:00Z', normalized: null,
  purpose: 'review', is_current: false, data_dates: null,
}
const brokenFile: DatasetOut = { ...reviewFile, id: 13, source_filename: 'broken.csv', validation: { ok: false, message: 'bad' } }

const planningRows = [
  { time: '08:00-09:00', lambda: 30, mu: 12, c: 3, rho: 0.8333, Wq: 0.05, stable: true, model: 'M/M/c', status: 'Peak' },
  { time: '09:00-10:00', lambda: 40, mu: 12, c: 3, rho: 1.111, Wq: null, stable: false, model: 'M/M/c', status: 'Unstable' },
  { time: '10:00-11:00', lambda: 20, mu: 12, c: 3, rho: 0.5556, Wq: 0.01, stable: true, model: 'M/M/c', status: 'Lean' },
]

function currentFor(dataset: DatasetOut) {
  if (dataset.id === 11) {
    return {
      analysis: analysis().analysis, dataset, selected_model: 'M/M/c', rows: planningRows, explanations: [],
      kpis: { avg_waiting_time: 0.03, unstable_count: 1, stable_count: 2 },
      arrivals_by_period: [{ time: '08:00-09:00', arrivals_per_hour: 30 }, { time: '09:00-10:00', arrivals_per_hour: 40 }, { time: '10:00-11:00', arrivals_per_hour: 20 }],
      busiest_period: { time: '09:00-10:00', arrivals_per_hour: 40 },
    }
  }
  return {
    analysis: analysis().analysis, dataset, selected_model: 'M/M/c', explanations: [],
    rows: [{ time: '07:00-08:00', lambda: 99, mu: 50, c: 3, rho: 0.66, Wq: 0.002, stable: true, model: 'M/M/c', status: 'Normal' }],
    kpis: { avg_waiting_time: 0.002, unstable_count: 0, stable_count: 1 },
    arrivals_by_period: [{ time: '07:00-08:00', arrivals_per_hour: 99 }],
    busiest_period: { time: '07:00-08:00', arrivals_per_hour: 99 },
  }
}

const planRows = [
  { time: '08:00-09:00', c_current: 3, c_optimal: 4, rho_current: 0.8333, rho_optimal: 0.625, Wq_current: 0.05, Wq_optimal: 0.01, Lq_optimal: 0.3,
    cost_current: 500, cost_optimal: 450, current_stable: true, optimized_stable: true },
  { time: '09:00-10:00', c_current: 3, c_optimal: 5, rho_current: 1.111, rho_optimal: 0.6667, Wq_current: null, Wq_optimal: 0.01, Lq_optimal: 0.4,
    cost_current: null, cost_optimal: 600, current_stable: false, optimized_stable: true },
]

function scenario(id: number, name: string, status: string, target = 0.7) {
  return {
    id, analysis_id: 7, dataset_id: 11, name, settings: { target_utilization: target, calculation: {} }, results: { results: planRows },
    created_at: '2026-10-10T00:00:00Z', provenance: 'verified_snapshot', evidence_status: status,
    evidence_reasons: status === 'CURRENT' ? [] : [{ code: 'DATASET_NOT_CURRENT', subject: 'scenario', detail: 'Made with an older file.' }],
  }
}

function workflowWith(selected: { id: number; name: string } | null) {
  return {
    analysis_id: 7, selection: selected ? { id: 1, kind: 'workflow_selection', status: 'completed', params: { scenario_id: selected.id }, result: {}, created_at: '', finished_at: '' } : null,
    scenario: selected ? { ...selected, dataset_id: 11, provenance: 'verified_snapshot', settings: {} } : null,
    des: null, des_current: null, mc: null, mc_current: null, validation: null, validation_current: null, decision: null, decision_stale: false,
  }
}

function Where() {
  const location = useLocation()
  return <output data-testid="where">{location.pathname}{location.search}</output>
}

function renderResults(route = '/results?analysis=7') {
  return renderWithProviders(
    <><Routes><Route path="/results" element={<ResultsPage />} /></Routes><Where /></>,
    { route },
  )
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue(analysis())
  listDatasetsMock.mockReset().mockResolvedValue({ datasets: [brokenFile, reviewFile, planningFile] })
  getCurrentMock.mockReset().mockImplementation(async (_id: number, datasetId?: number) => currentFor(datasetId === 12 ? reviewFile : planningFile))
  getObservedMock.mockReset().mockResolvedValue({
    analysis_id: 7, dataset_id: 11, available: true, flagged_any: false, day_modeled_wait: 0.03, day_observed_wait: 0.1, ratio: 2, min_gap_minutes: 1,
    periods: [{ time: '08:00-09:00', modeled_wait: 0.05, observed_wait: 0.12, flagged: false }],
  })
  getWorkflowMock.mockReset().mockResolvedValue(workflowWith(null))
  listScenariosMock.mockReset().mockResolvedValue({ scenarios: [] })
  getSeparateMock.mockReset()
  selectMock.mockReset().mockResolvedValue({ selection: {} })
})

function keyResult(name: string) {
  return screen.getByRole('heading', { name }).closest('section') as HTMLElement
}

describe('Analysis results: the planning file', () => {
  it('identifies the only saved plan as already selected without creating another selection', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Only saved plan' }))
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Only saved plan', 'CURRENT')] })
    renderResults()
    const status = await screen.findByText('Only saved plan is the selected scenario for simulation.')
    expect(status).toHaveAttribute('role', 'status')
    expect(screen.getByLabelText('Plan')).toHaveValue('3')
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
    expect(selectMock).not.toHaveBeenCalled()
  })

  it('updates the plan selector when the server selection changes while results remains open', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Plan A' }))
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Plan A', 'CURRENT'), scenario(4, 'Plan B', 'CURRENT')] })
    const { queryClient } = renderResults()
    expect(await screen.findByLabelText('Plan')).toHaveValue('3')
    act(() => { queryClient.setQueryData(['workflow', 7], workflowWith({ id: 4, name: 'Plan B' })) })
    await waitFor(() => expect(screen.getByLabelText('Plan')).toHaveValue('4'))
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
  })

  it('discards an unavailable draft plan instead of reviving it when the option reappears', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Plan A' }))
    const planA = scenario(3, 'Plan A', 'CURRENT')
    const planB = scenario(4, 'Plan B', 'CURRENT')
    listScenariosMock.mockResolvedValue({ scenarios: [planA, planB] })
    const { queryClient } = renderResults()
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('Plan'), '4')
    act(() => { queryClient.setQueryData(['scenarios', 7], { scenarios: [planA] }) })
    await waitFor(() => expect(screen.getByLabelText('Plan')).toHaveValue('3'))
    act(() => { queryClient.setQueryData(['scenarios', 7], { scenarios: [planA, planB] }) })
    await waitFor(() => expect(screen.getByLabelText('Plan')).toHaveValue('3'))
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
    expect(selectMock).not.toHaveBeenCalled()
  })

  it('resets a draft plan when the active analysis changes with the selector still mounted', async () => {
    const planA = scenario(3, 'Plan A', 'CURRENT')
    const planB = scenario(4, 'Plan B', 'CURRENT')
    const otherPlan = { ...scenario(13, 'Other analysis plan', 'CURRENT'), analysis_id: 8 }
    const { rerender } = renderWithProviders(<PlanChanges analysisId={7} plan={{
      kind: 'shared', scenario: planA, scenarios: [planA, planB], usable: true, target: 0.7,
    }} />)
    const user = userEvent.setup()
    await user.selectOptions(screen.getByLabelText('Plan'), '4')
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeEnabled()
    rerender(<PlanChanges analysisId={8} plan={{
      kind: 'shared', scenario: otherPlan, scenarios: [otherPlan], usable: true, target: 0.7,
    }} />)
    expect(screen.getByLabelText('Plan')).toHaveValue('13')
    expect(screen.getByText('Other analysis plan is the selected scenario for simulation.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
    expect(selectMock).not.toHaveBeenCalled()
  })

  it('switches between saved plans and confirms each successful server selection', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Plan A' }))
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Plan A', 'CURRENT'), scenario(4, 'Plan B', 'CURRENT')] })
    selectMock.mockImplementation(async (_analysisId: number, id: number) => {
      getWorkflowMock.mockResolvedValue(workflowWith({ id, name: id === 3 ? 'Plan A' : 'Plan B' }))
      return { selection: {} }
    })
    const user = userEvent.setup()
    renderResults()
    await user.selectOptions(await screen.findByLabelText('Plan'), '4')
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    expect(await screen.findByText('Plan B is the selected scenario for simulation.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Plan'), '3')
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    expect(await screen.findByText('Plan A is the selected scenario for simulation.')).toBeInTheDocument()
    expect(selectMock.mock.calls).toEqual([[7, 4], [7, 3]])
  })

  it('selects an eligible saved plan before any selection exists, without saving or generating another plan', async () => {
    const user = userEvent.setup()
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Saved plan', 'CURRENT'), scenario(4, 'Old plan', 'STALE')] })
    selectMock.mockImplementation(async () => {
      getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Saved plan' }))
      return { selection: {} }
    })
    renderResults()
    const choice = await screen.findByLabelText('Plan')
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
    expect(within(choice).queryByRole('option', { name: 'Old plan' })).not.toBeInTheDocument()
    await user.selectOptions(choice, '3')
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    await waitFor(() => expect(selectMock).toHaveBeenCalledWith(7, 3))
    expect(await screen.findByText('Calculated result · not yet checked by simulation')).toBeInTheDocument()
  })

  it('keeps an unselected saved plan available after a selection refusal, and allows a retry', async () => {
    const user = userEvent.setup()
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Saved plan', 'CURRENT')] })
    selectMock.mockRejectedValueOnce({ response: { data: { detail: 'Plan needs recalculation.' } } })
    renderResults()
    await user.selectOptions(await screen.findByLabelText('Plan'), '3')
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Plan needs recalculation.')
    expect(screen.getByRole('option', { name: 'Saved plan' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    await waitFor(() => expect(selectMock).toHaveBeenCalledTimes(2))
  })

  it('offers the first separate saved plan while excluding invalid and stale plans', async () => {
    const user = userEvent.setup()
    getAnalysisMock.mockResolvedValue(analysis('separate_queues'))
    getSeparateMock.mockResolvedValue({ analysis_id: 7, selected_scenario_id: null, plans: [
      { scenario_id: 21, name: 'Eligible lanes', valid: true, stale: false },
      { scenario_id: 22, name: 'Invalid lanes', valid: false, stale: false },
      { scenario_id: 23, name: 'Old lanes', valid: true, stale: true },
    ] })
    renderResults()
    const choice = await screen.findByLabelText('Plan')
    expect(within(choice).getAllByRole('option').map((option) => option.textContent)).toEqual(['Choose a saved plan', 'Eligible lanes'])
    await user.selectOptions(choice, '21')
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    await waitFor(() => expect(selectMock).toHaveBeenCalledWith(7, 21))
    expect(getWorkflowMock).not.toHaveBeenCalled()
  })

  it('does not offer incomplete or historical snapshots for the first selection', async () => {
    listScenariosMock.mockResolvedValue({ scenarios: [
      scenario(3, 'Historical', 'HISTORICAL_REQUIRES_RECALCULATION'),
      { ...scenario(4, 'Incomplete', 'CURRENT'), results: { results: [] } },
      { ...scenario(5, 'Unverified', 'CURRENT'), provenance: 'legacy' },
    ] })
    renderResults()
    expect(await screen.findByText('No plan is selected yet. Choose one in Suggested plans to see what it changes.')).toBeInTheDocument()
    expect(screen.queryByLabelText('Plan')).not.toBeInTheDocument()
  })

  it('opens the planning file with its dates, tags and key results from the server', async () => {
    renderResults()
    expect(await screen.findByRole('heading', { name: 'Recorded average wait' })).toBeInTheDocument()
    const picker = screen.getByLabelText('View Results from')
    expect(picker).toHaveValue('11')
    expect(within(picker).getAllByRole('option').map((option) => option.textContent)).toEqual([
      'feb_totals.csv · Data period unavailable · Review only',
      'march_records.csv · Mar 1 – Mar 31, 2026 · Planning file',
    ])
    expect(screen.getByText('Mar 1 – Mar 31, 2026', { selector: 'dd' })).toBeInTheDocument()
    expect(within(keyResult('Recorded average wait')).getByText('6 min')).toBeInTheDocument()
    expect(within(keyResult('Estimated average wait')).getByText('1.8 min')).toBeInTheDocument()
    expect(within(keyResult('Estimated average wait')).getByText('Leaves out 1 period where counters can\'t keep up.')).toBeInTheDocument()
    expect(within(keyResult('Busiest period by customer arrivals')).getByText('09:00-10:00')).toBeInTheDocument()
    expect(within(keyResult('Busiest period by customer arrivals')).getByText('40 customers per hour')).toBeInTheDocument()
    expect(getCurrentMock).toHaveBeenCalledWith(7, undefined)
    expect(getObservedMock).toHaveBeenCalledWith(7, undefined)
    expect(screen.queryByTestId('results-review-banner')).not.toBeInTheDocument()
  })

  it('lists periods where counters can\'t keep up before the highest-wait period', async () => {
    renderResults()
    const card = keyResult(await screen.findByRole('heading', { name: 'Period that needs attention' }).then((node) => node.textContent ?? ''))
    const overloaded = within(card).getByText(/09:00-10:00/)
    const highest = within(card).getByText(/Then highest estimated wait:/)
    expect(overloaded.compareDocumentPosition(highest) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy()
    expect(highest).toHaveTextContent('Then highest estimated wait: 08:00-09:00 · 3 min')
    expect(within(card).getByText('Not the longest wait any one customer had.')).toBeInTheDocument()
  })

  it('says when no plan is selected and flags no plan target', async () => {
    const user = userEvent.setup()
    renderResults()
    const prompt = await screen.findByText('No plan is selected yet. Choose one in Suggested plans to see what it changes.')
    // OD-4: the wait tab shows today's view with the no-plan prompt under the chart, and no Plan view.
    expect(within(screen.getByTestId('wait-by-hour')).getByText(prompt.textContent ?? '')).toBe(prompt)
    expect(screen.queryByRole('group', { name: 'Chart view' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Your day, by Busy Level' }))
    const strip = screen.getByRole('heading', { name: 'Your day, by Busy Level' }).closest('section') as HTMLElement
    expect(within(strip).getByRole('status')).toHaveTextContent("09:00-10:00: Can't keep up (100% or more)")
    expect(screen.queryByText(/above this plan's target/)).not.toBeInTheDocument()
    expect(screen.queryByText('Calculated result · not yet checked by simulation')).not.toBeInTheDocument()
  })

  it('shows what a current plan changes, its target flags and the calculated result without decision words', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Plan A' }))
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Plan A', 'CURRENT'), scenario(4, 'Plan B', 'CURRENT', 0.8), scenario(5, 'Old plan', 'STALE_DATASET')] })
    const user = userEvent.setup()
    renderResults()
    expect(await screen.findByText('Calculated result · not yet checked by simulation')).toBeInTheDocument()
    expect(screen.getByText('The calculation suggests these counter changes: 08:00-09:00: 3 → 4 counters; 09:00-10:00: 3 → 5 counters.')).toBeInTheDocument()
    // Shared lines: both sides are calculated, so the wait line keeps its wording and no cost-basis label is added.
    expect(screen.getByText('Estimated wait (average of the periods): Unavailable → 0.6 min.')).toBeInTheDocument()
    expect(screen.queryByText(/per average day|total for \d+ days/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Your day, by Busy Level' }))
    expect(screen.getAllByText(/above this plan's target of 70%/).length).toBeGreaterThan(0)
    // Today's cost is unknown while counters can't keep up: never a partial total.
    expect(screen.getByText('Total cost: Unavailable → Unavailable.', { exact: false })).toBeInTheDocument()
    expect(document.body.textContent).not.toMatch(/adopt|go ahead/i)
    const switcher = screen.getByLabelText('Plan')
    expect(within(switcher).getAllByRole('option').map((option) => option.textContent)).toEqual(['Plan A', 'Plan B'])
    expect(screen.getByRole('button', { name: 'Use for simulation' })).toBeDisabled()
  })

  it('uses another current plan for simulation and shows a server refusal', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith({ id: 3, name: 'Plan A' }))
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(3, 'Plan A', 'CURRENT'), scenario(4, 'Plan B', 'CURRENT')] })
    selectMock.mockRejectedValueOnce(Object.assign(new Error('409'), { response: { status: 409, data: { detail: 'Plan B is not current.' } } }))
    const user = userEvent.setup()
    renderResults()
    await user.selectOptions(await screen.findByLabelText('Plan'), '4')
    await user.click(screen.getByRole('button', { name: 'Use for simulation' }))
    await waitFor(() => expect(selectMock).toHaveBeenCalledWith(7, 4))
    expect(await screen.findByRole('alert')).toHaveTextContent('Plan B is not current.')
  })

  it('never shows the numbers of a plan that is no longer current', async () => {
    getWorkflowMock.mockResolvedValue({ ...workflowWith(null), selection_evidence: { scenario_id: 5, evidence_status: 'STALE_DATASET', evidence_reasons: [] } })
    listScenariosMock.mockResolvedValue({ scenarios: [scenario(5, 'Old plan', 'STALE_DATASET')] })
    renderResults()
    expect(await screen.findByText(/"Old plan" no longer matches your current data or setup/)).toBeInTheDocument()
    expect(screen.getByText('Made with an older file.')).toBeInTheDocument()
    expect(screen.queryByText('Calculated result · not yet checked by simulation')).not.toBeInTheDocument()
    expect(screen.queryByText(/above this plan's target/)).not.toBeInTheDocument()
    expect(screen.queryByText('Old plan is the selected scenario for simulation.')).not.toBeInTheDocument()
  })

  it('keeps the chosen period in the address and shows its numbers', async () => {
    const user = userEvent.setup()
    renderResults()
    await user.click(await screen.findByRole('tab', { name: 'Your day, by Busy Level' }))
    await user.click(screen.getByRole('button', { name: '08:00-09:00: Peak, 83.33%' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/results?analysis=7&chart=level&period=08%3A00-09%3A00')
    const summary = screen.getByRole('heading', { name: 'Current operation by period' }).closest('section') as HTMLElement
    expect(within(summary).getAllByText('3 min').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('link', { name: 'Inputs and model' }))
    const panel = screen.getByRole('table', { name: "Every period's numbers" })
    expect(within(panel).getByText('83.33%')).toBeInTheDocument()
  })
})

describe('Analysis results: another file', () => {
  it('reads a review-only file by its id, says so, and never touches plans or simulation', async () => {
    renderResults('/results?analysis=7&file=12')
    expect(await screen.findByTestId('results-review-banner')).toHaveTextContent('You are reviewing a previous file. Your current staffing plan has not changed.')
    expect(screen.getByTestId('results-review-banner')).toHaveTextContent('Calculated today from the inputs saved with this file. Results from the upload day were not saved.')
    await waitFor(() => expect(within(keyResult('Busiest period by customer arrivals')).getByText('07:00-08:00')).toBeInTheDocument())
    expect(getCurrentMock).toHaveBeenCalledWith(7, 12)
    expect(screen.getByText('Recorded waiting time is unavailable because this file does not contain customer arrival and service-start times.')).toBeInTheDocument()
    expect(getObservedMock).not.toHaveBeenCalled()
    expect(getWorkflowMock).not.toHaveBeenCalled()
    expect(listScenariosMock).not.toHaveBeenCalled()
    expect(getSeparateMock).not.toHaveBeenCalled()
    expect(selectMock).not.toHaveBeenCalled()
    expect(screen.queryByText('What the plan changes')).not.toBeInTheDocument()
  })

  it('clears the previous file\'s values while the next file loads', async () => {
    let release: () => void = () => {}
    const user = userEvent.setup()
    renderResults()
    await waitFor(() => expect(within(keyResult('Busiest period by customer arrivals')).getByText('09:00-10:00')).toBeInTheDocument())
    getCurrentMock.mockImplementation(async (_id: number, datasetId?: number) => {
      await new Promise<void>((resolve) => { release = resolve })
      return currentFor(datasetId === 12 ? reviewFile : planningFile)
    })
    await user.selectOptions(screen.getByLabelText('View Results from'), '12')
    expect(screen.getByTestId('where')).toHaveTextContent('/results?analysis=7&file=12')
    expect(screen.queryByRole('heading', { name: 'Busiest period by customer arrivals' })).not.toBeInTheDocument()
    expect(screen.queryByText('6 min')).not.toBeInTheDocument()
    expect(screen.queryByText('40 customers per hour')).not.toBeInTheDocument()
    release()
    await waitFor(() => expect(within(keyResult('Busiest period by customer arrivals')).getByText('07:00-08:00')).toBeInTheDocument())
    expect(screen.queryByText('40 customers per hour')).not.toBeInTheDocument()
  })

  it('shows Unavailable, never zero, for missing values', async () => {
    getCurrentMock.mockResolvedValue({
      ...currentFor(planningFile), kpis: { avg_waiting_time: null, unstable_count: 0 }, busiest_period: null, arrivals_by_period: [],
      rows: [{ time: '08:00-09:00', lambda: null, mu: null, c: null, rho: null, Wq: null, stable: true }],
    })
    getObservedMock.mockResolvedValue({ analysis_id: 7, dataset_id: 11, available: false, periods: [], flagged_any: false, day_modeled_wait: null, day_observed_wait: null, ratio: 2, min_gap_minutes: 1 })
    renderResults()
    expect(await screen.findByRole('heading', { name: 'Estimated average wait' })).toBeInTheDocument()
    for (const name of ['Recorded average wait', 'Estimated average wait', 'Period that needs attention', 'Busiest period by customer arrivals']) {
      await waitFor(() => expect(within(keyResult(name)).getByText('Unavailable')).toBeInTheDocument())
      expect(within(keyResult(name)).queryByText(/^0/)).not.toBeInTheDocument()
    }
    expect(screen.getByText('Customers per hour are unavailable for this file.')).toBeInTheDocument()
  })

  it('falls back to the planning file when the address names a file that is not processed', async () => {
    renderResults('/results?analysis=7&file=13')
    expect(await screen.findByLabelText('View Results from')).toHaveValue('11')
    expect(getCurrentMock).not.toHaveBeenCalledWith(7, 13)
  })
})

describe('Inputs and model reference', () => {
  it('retains file/period/line through native links and preserves review-only request guards', async () => {
    const user = userEvent.setup()
    renderResults('/results?analysis=7&file=12&period=07%3A00-08%3A00&line=queue_a')
    const link = await screen.findByRole('link', { name: 'Inputs and model' })
    expect(link).toHaveAttribute('href', '/results?analysis=7&file=12&period=07%3A00-08%3A00&line=queue_a&view=reference')
    await user.click(link)
    expect(screen.getByRole('heading', { level: 1, name: 'Inputs and model' })).toHaveFocus()
    expect(screen.queryByRole('heading', { name: 'Recorded average wait' })).not.toBeInTheDocument()
    const back = screen.getByRole('link', { name: 'Return to analysis results' })
    expect(back).toHaveAttribute('href', '/results?analysis=7&file=12&period=07%3A00-08%3A00&line=queue_a')
    await user.click(back)
    expect(screen.getByRole('heading', { level: 1, name: 'Analysis Results' })).toHaveFocus()
    for (const mock of [getWorkflowMock, listScenariosMock, getSeparateMock, selectMock]) expect(mock).not.toHaveBeenCalled()
    expect(getCurrentMock).toHaveBeenCalledWith(7, 12)
  })

  it('opens a deep link with every returned model explanation and input intact', async () => {
    getCurrentMock.mockResolvedValue({ ...currentFor(reviewFile), explanations: [{
      time: '07:00-08:00', queue_id: null, selected_model: 'M/M/c', selection_reason: 'Source model reason',
      operational_facts: ['Source operating fact'], measured_characteristics: ['Source measured input'], model_assumptions: ['Source assumption'],
    }] })
    renderResults('/results?analysis=7&file=12&view=reference&period=07%3A00-08%3A00')
    const table = await screen.findByRole('table')
    expect(within(table).getByText('99')).toBeInTheDocument()
    expect(within(table).getByText('50')).toBeInTheDocument()
    await userEvent.setup().click(screen.getByText('07:00-08:00: M/M/c', { selector: 'summary' }))
    for (const text of ['Source model reason', 'Source operating fact', 'Source measured input', 'Source assumption']) expect(screen.getByText(text)).toBeVisible()
    expect(screen.getAllByRole('heading', { level: 1 })).toHaveLength(1)
    for (const mock of [getWorkflowMock, listScenariosMock, getSeparateMock, selectMock]) expect(mock).not.toHaveBeenCalled()
  })

  it('keeps the default concise while charts retain exact values, flags and units as semantic lists', async () => {
    getObservedMock.mockResolvedValue({ dataset_id: 11, available: true, day_observed_wait: 0.1,
      periods: [{ time: '08:00-09:00', modeled_wait: 0.05, observed_wait: 0.12, flagged: true }] })
    renderResults()
    await screen.findByRole('heading', { name: 'Recorded average wait' })
    expect(screen.queryByText("Every period's numbers")).not.toBeInTheDocument()
    expect(screen.queryByText('How was this calculated?')).not.toBeInTheDocument()
    expect(screen.queryByRole('img')).not.toBeInTheDocument()
    const arrivals = screen.getByRole('list', { name: 'Customers per hour, by period' })
    expect(within(arrivals).getByText('40 customers per hour')).toBeInTheDocument()
    expect(screen.getByRole('group', { name: 'Wait by period. Use the arrow keys to read each period.' })).toBeInTheDocument()
    const table = within(screen.getByRole('region', { name: 'Show as a table' })).getByRole('table')
    expect(within(table).getByText('7.2 min')).toBeInTheDocument()
    expect(within(table).getByText('3 min')).toBeInTheDocument()
    expect(within(table).getByText('Much longer than modeled')).toBeInTheDocument()
  })

  it('does not show recorded wait from a mismatched file response', async () => {
    getObservedMock.mockResolvedValue({ dataset_id: 999, available: true, day_observed_wait: 100, periods: [] })
    renderResults()
    await screen.findByRole('heading', { name: 'Recorded average wait' })
    expect(within(keyResult('Recorded average wait')).getByText('Unavailable')).toBeInTheDocument()
    expect(screen.queryByText('6000 min')).not.toBeInTheDocument()
  })
})

describe('Analysis results: separate lines', () => {
  it('shows today\'s cost as unavailable with the reason and offers only valid current plans', async () => {
    getAnalysisMock.mockResolvedValue(analysis('separate_queues'))
    getCurrentMock.mockResolvedValue({
      ...currentFor(planningFile),
      rows: [
        { time: '08:00-09:00', queue_id: 'A', lambda: 9, mu: 12, c: 1, rho: 0.75, Wq: 0.25, stable: true, queue_structure: 'separate_queues' },
        { time: '08:00-09:00', queue_id: 'B', lambda: 1, mu: 12, c: 1, rho: 0.0833, Wq: 0.01, stable: true, queue_structure: 'separate_queues' },
      ],
      busiest_period: { time: '08:00-09:00', arrivals_per_hour: 10 },
    })
    getSeparateMock.mockResolvedValue({
      analysis_id: 7, queue_structure: 'separate_queues', selected_scenario_id: 21,
      current: { dataset_id: 11, wait_mean: 0.2, wait_basis: 'analytical', util_max: 0.75, waiting_cost: 10, waiting_cost_basis: null, total_cost: null,
        total_cost_reason: 'Current staffing costs are not stored for separate lines.',
        periods: [{ time: '08:00-09:00', active_lanes: ['A', 'B'], lambda_total: 10, wait_mean: 0.2, util_max: 0.75 }] },
      plans: [
        { scenario_id: 21, name: 'Lanes plan', dataset_id: 11, target: 0.7, evaluation_method: 'DES_REPLICATIONS', replications: 5, base_seed: 1, overall: null,
          stale: false, valid: true, valid_reason: null, totals: { lane_periods: 3, wait_mean: 0.1, peak_util: 0.6, waiting_cost_mean: 5, total_cost_mean: 320 },
          periods: [{ time: '08:00-09:00', current_active_lanes: ['A', 'B'], optimal_active_lanes: 3, adjustment: 1, peak_util: 0.6, wait_mean: 0.1, wait_ci: null, waiting_cost_mean: 5, total_cost_mean: 320, total_cost_ci: null, status: null }] },
        { scenario_id: 22, name: 'Broken plan', dataset_id: 11, target: 0.7, evaluation_method: null, replications: null, base_seed: null, overall: null,
          stale: false, valid: false, valid_reason: 'Missing periods.', totals: null, periods: [] },
      ],
    })
    renderResults()
    expect(await screen.findByText('Today\'s total cost is not available: Current staffing costs are not stored for separate lines.')).toBeInTheDocument()
    expect(within(screen.getByLabelText('Plan')).getAllByRole('option').map((option) => option.textContent)).toEqual(['Lanes plan'])
    expect(screen.getByText('For separate lines, the plan\'s values come from the optimizer\'s routing simulation. This is still not the full simulation check.')).toBeInTheDocument()
    expect(within(keyResult('Busiest period by customer arrivals')).getByText('10 customers per hour')).toBeInTheDocument()
    expect(screen.getAllByText(/above this plan's target of 70%/).length).toBeGreaterThan(0)
    expect(getWorkflowMock).not.toHaveBeenCalled()
  })
})

describe('Analysis results: chart tabs (spec 2026-10-29 §5.1)', () => {
  it('opens "What the plan changes" first, moves with arrow keys, Home and End, and keeps the tab in the address', async () => {
    const user = userEvent.setup()
    renderResults()
    const list = await screen.findByRole('tablist', { name: 'Analysis Results charts' })
    const tabs = within(list).getAllByRole('tab')
    expect(tabs.map((tab) => tab.textContent)).toEqual(['What the plan changes', 'Your day, by Busy Level'])
    expect(tabs[0]).toHaveAttribute('aria-selected', 'true')
    expect(tabs[0]).toHaveAttribute('tabindex', '0')
    expect(tabs[1]).toHaveAttribute('tabindex', '-1')
    expect(screen.getByRole('tabpanel')).toHaveAttribute('aria-labelledby', tabs[0].id)
    tabs[0].focus()
    await user.keyboard('{ArrowRight}')
    expect(screen.getByRole('tab', { name: 'Your day, by Busy Level' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByRole('tab', { name: 'Your day, by Busy Level' })).toHaveFocus()
    expect(screen.getByTestId('where')).toHaveTextContent('chart=level')
    expect(screen.getByTestId('busy-level')).toBeInTheDocument()
    expect(screen.queryByTestId('wait-by-hour')).not.toBeInTheDocument()
    await user.keyboard('{Home}')
    expect(screen.getByRole('tab', { name: 'What the plan changes' })).toHaveFocus()
    expect(screen.getByTestId('where')).toHaveTextContent('chart=wait')
    await user.keyboard('{End}')
    expect(screen.getByRole('tab', { name: 'Your day, by Busy Level' })).toHaveFocus()
    await user.keyboard('{ArrowLeft}')
    expect(screen.getByRole('tab', { name: 'What the plan changes' })).toHaveAttribute('aria-selected', 'true')
  })

  it('opens the tab named in the address', async () => {
    renderResults('/results?analysis=7&chart=level')
    expect(await screen.findByTestId('busy-level')).toBeInTheDocument()
    expect(screen.getByRole('tab', { name: 'Your day, by Busy Level' })).toHaveAttribute('aria-selected', 'true')
  })

  it('falls back to the first available tab for an unknown name', async () => {
    renderResults('/results?analysis=7&chart=other')
    expect(await screen.findByTestId('wait-by-hour')).toBeInTheDocument()
  })

  it('keeps the no-plan prompt visible when the address opens the Busy Level tab (review K-UC-2)', async () => {
    const user = userEvent.setup()
    renderResults('/results?analysis=7&chart=level')
    expect(await screen.findByTestId('busy-level')).toBeInTheDocument()
    const prompt = await screen.findByText('No plan is selected yet. Choose one in Suggested plans to see what it changes.')
    expect(screen.getByRole('tabpanel')).not.toContainElement(prompt)
    expect(screen.getAllByText(prompt.textContent ?? '')).toHaveLength(1)
    // Back on the wait tab, the prompt moves under the chart and is not repeated.
    await user.click(screen.getByRole('tab', { name: 'What the plan changes' }))
    const again = screen.getByText(prompt.textContent ?? '')
    expect(within(screen.getByTestId('wait-by-hour')).getByText(prompt.textContent ?? '')).toBe(again)
    expect(screen.getAllByText(prompt.textContent ?? '')).toHaveLength(1)
  })

  it('shows a single card without a tablist when only Busy Level has content, and the no-plan prompt below', async () => {
    getObservedMock.mockResolvedValue({ analysis_id: 7, dataset_id: 11, available: false, periods: [], flagged_any: false, day_modeled_wait: null, day_observed_wait: null, ratio: 2, min_gap_minutes: 1 })
    renderResults()
    expect(await screen.findByTestId('busy-level')).toBeInTheDocument()
    expect(screen.queryByRole('tablist')).not.toBeInTheDocument()
    expect(screen.queryByTestId('wait-by-hour')).not.toBeInTheDocument()
    expect(await screen.findByText('No plan is selected yet. Choose one in Suggested plans to see what it changes.')).toBeInTheDocument()
  })
})

describe('Analysis results: separate plan cost by day basis (spec 2026-10-29 §6)', () => {
  function separateSetup(basis: 'representative_day' | 'per_date') {
    const base = analysis('separate_queues')
    // 60-minute Setup segments: the period costs are hourly rates added up, so only then is the sum a day's cost (K-UC-1).
    const segments = [{ id: 'morning', start_time: '08:00', end_time: '09:00', active_queue_ids: null }, { id: 'noon', start_time: '12:00', end_time: '13:00', active_queue_ids: null }]
    return { analysis: { ...base.analysis, queue_setup: { ...base.analysis.queue_setup, segments, event_period_basis: basis } } }
  }
  function comparisonWith(periods: { time: string; cost: number }[], total: number) {
    return {
      analysis_id: 7, queue_structure: 'separate_queues', selected_scenario_id: 21,
      current: { dataset_id: 11, wait_mean: 0.2, wait_basis: 'analytical', util_max: 0.75, waiting_cost: 10, waiting_cost_basis: null, total_cost: null,
        total_cost_reason: 'Current staffing costs are not stored for separate lines.',
        periods: periods.map((item) => ({ time: item.time, active_lanes: ['A', 'B'], lambda_total: 10, wait_mean: 0.2, util_max: 0.75 })) },
      plans: [{ scenario_id: 21, name: 'Lanes plan', dataset_id: 11, target: 0.7, evaluation_method: 'DES_REPLICATIONS', replications: 5, base_seed: 1, overall: null,
        wait_basis_kind: 'simulation', stale: false, valid: true, valid_reason: null,
        totals: { lane_periods: periods.length * 2, wait_mean: 0.1, peak_util: 0.6, waiting_cost_mean: 5, total_cost_mean: total },
        periods: periods.map((item) => ({ time: item.time, current_active_lanes: ['A', 'B'], optimal_active_lanes: 2, adjustment: 0, peak_util: 0.6, wait_mean: 0.1,
          wait_ci: [-0.0239, 0.3], waiting_cost_mean: 5, total_cost_mean: item.cost, total_cost_ci: null, status: null })) }],
    }
  }
  function currentWith(times: string[]) {
    return { ...currentFor(planningFile), rows: times.flatMap((time) => [
      { time, queue_id: 'A', lambda: 9, mu: 12, c: 1, rho: 0.75, Wq: 0.25, stable: true, queue_structure: 'separate_queues' },
      { time, queue_id: 'B', lambda: 1, mu: 12, c: 1, rho: 0.0833, Wq: 0.01, stable: true, queue_structure: 'separate_queues' },
    ]) }
  }

  it('labels a representative-day plan cost with the days of data and names both kinds in the wait line', async () => {
    getAnalysisMock.mockResolvedValue(separateSetup('representative_day'))
    const file = { ...planningFile, validation: { ...planningFile.validation, period_basis: 'representative_day', observation_days: 14 } }
    listDatasetsMock.mockResolvedValue({ datasets: [file] })
    getCurrentMock.mockResolvedValue(currentWith(['morning', 'noon']))
    getSeparateMock.mockResolvedValue(comparisonWith([{ time: 'morning', cost: 200.5 }, { time: 'noon', cost: 119.5 }], 320))
    renderResults()
    expect(await screen.findByTestId('plan-cost')).toHaveTextContent('Unavailable → ₱320 per average day (from 14 days of data)')
    expect(screen.getByText(/^Total cost: Unavailable → ₱320 per average day \(from 14 days of data\)\./)).toBeInTheDocument()
    expect(screen.getByText('Wait (average of the periods): Calculated estimate 12 min → Suggested plan, simulated 6 min.')).toBeInTheDocument()
  })

  it('labels a per-date plan cost with the distinct dates and the data period', async () => {
    getAnalysisMock.mockResolvedValue(separateSetup('per_date'))
    const file = { ...planningFile, data_dates: { first: '2026-03-01', last: '2026-03-02', source: 'stored_at_upload' as const } }
    listDatasetsMock.mockResolvedValue({ datasets: [file] })
    const times = ['2026-03-01 morning UTC', '2026-03-01 noon UTC', '2026-03-02 morning UTC']
    getCurrentMock.mockResolvedValue(currentWith(times))
    getSeparateMock.mockResolvedValue(comparisonWith(times.map((time, index) => ({ time, cost: 100 + index })), 303))
    renderResults()
    expect(await screen.findByTestId('plan-cost')).toHaveTextContent('₱303 total for 2 days (2026-03-01 – 2026-03-02)')
  })

  it('shows no label when the plan total is not the sum of its periods', async () => {
    getAnalysisMock.mockResolvedValue(separateSetup('representative_day'))
    const file = { ...planningFile, validation: { ...planningFile.validation, period_basis: 'representative_day', observation_days: 14 } }
    listDatasetsMock.mockResolvedValue({ datasets: [file] })
    getCurrentMock.mockResolvedValue(currentWith(['morning', 'noon']))
    getSeparateMock.mockResolvedValue(comparisonWith([{ time: 'morning', cost: 200 }, { time: 'noon', cost: 100 }], 320))
    renderResults()
    expect(await screen.findByTestId('plan-cost')).toHaveTextContent(/Unavailable → ₱320$/)
    expect(screen.queryByText(/per average day/)).not.toBeInTheDocument()
  })
})
