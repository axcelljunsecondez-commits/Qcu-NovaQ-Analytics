import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { DecisionEndpointPage } from './DecisionEndpointPage'

const getWorkflowMock = vi.fn()
const createDecisionMock = vi.fn()
const runSelectedDecisionMock = vi.fn()
const getAnalysisMock = vi.fn()

vi.mock('../../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  createWorkflowDecision: (...args: unknown[]) => createDecisionMock(...args),
  runSelectedDecision: (...args: unknown[]) => runSelectedDecisionMock(...args),
}))

vi.mock('../../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
}))

function analysisWith(queueStructure: string) {
  return { analysis: { id: 7, name: 'A', queue_setup: { queue_structure: queueStructure } } }
}

vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const insufficient = {
  status: 'insufficient_evidence',
  headline: 'Insufficient evidence to make a management recommendation.',
  recommendation: 'Complete the missing workflow evidence before making an adoption decision.',
  rationale: ['Missing: a completed Scenario Validation run.'],
  missing_evidence: ['a completed Scenario Validation run'],
  scenario_id: 3,
  scenario_name: 'Plan A',
  dataset_id: 2,
  evidence_ids: { selection: 1, des: 2, mc: null, validation: null },
  provenance_warning: 'Analytical estimates and simulated results are decision support.',
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId/decision" element={<DecisionEndpointPage />} />
    </Routes>,
    { route: '/analyses/7/decision' },
  )
}

beforeEach(() => {
  getWorkflowMock.mockReset().mockResolvedValue({
    analysis_id: 7,
    selection: null,
    scenario: null,
    des: null,
    mc: null,
    validation: null,
    decision: null,
    decision_stale: false,
  })
  createDecisionMock.mockReset().mockResolvedValue({ decision: insufficient, persisted: true })
  runSelectedDecisionMock.mockReset()
  getAnalysisMock.mockReset().mockResolvedValue(analysisWith('shared_queue'))
})

describe('DecisionEndpointPage', () => {
  it('uses Separate context and exposes unassessed mean-load uncertainty beside a saved conditional result', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    getWorkflowMock.mockResolvedValue({ decision_stale: false, decision: { result: {
      ...insufficient, provenance: 'SELECTED', status: 'conditional', missing_evidence: [],
      recommendation: 'Original saved wording.', facts: { validation_checks: 60, failed_checks: 0 },
    } } })
    renderPage()
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent('Saved checks passed for this run. Savings cannot be compared.')
    expect(screen.getByTestId('decision-plain')).not.toHaveTextContent('costs more than today')
    expect(screen.getByTestId('selected-decision-scope')).toHaveTextContent('Load estimate uncertainty: Not checked.')
    expect(screen.getByText('Original saved wording.')).toBeInTheDocument()
    expect(runSelectedDecisionMock).not.toHaveBeenCalled()
    expect(createDecisionMock).not.toHaveBeenCalled()
  })

  it('shows the approved notice instead of the legacy label for v1 selected-load evidence', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    getWorkflowMock.mockResolvedValue({ decision_stale: false, decision: { result: {
      ...insufficient, provenance: 'SELECTED', status: 'conditional', missing_evidence: [], selected_load_method: 'selected-load-truncated-hoeffding-v1',
      recommendation: 'Original saved wording.', facts: { validation_checks: 60, failed_checks: 0 },
    } } })
    renderPage()
    const scope = await screen.findByTestId('selected-decision-scope')
    expect(scope).toHaveTextContent('Validation checks uncertainty in the average customer load estimated by simulation. Unsupported or inconclusive checks remain Insufficient evidence. This does not establish seed stability or future operational safety.')
    expect(scope).not.toHaveTextContent('Load estimate uncertainty: Not checked.')
    // OQ-4 (owner): the scope details stay in the v1 details.
    expect(screen.getByText(/Repeating the simulation with another seed/)).toBeInTheDocument()
  })

  it('reads an inconclusive v1 Decision as not enough data in its periods, not a missing run (OQ-1)', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    getWorkflowMock.mockResolvedValue({ decision_stale: false, decision: { result: {
      ...insufficient, provenance: 'SELECTED', missing_evidence: [], inadequate_periods: ['08:00', '09:00'],
      selected_load_method: 'selected-load-truncated-hoeffding-v1',
      recommendation: 'The completed checks could not show whether this plan passes in every period. Do not adopt it on this run alone; review the plan and its estimated loads first.',
      rationale: ['Selected Scenario: Plan A (ID 3).', 'Inadequate periods: 08:00, 09:00.'],
      facts: { validation_checks: 4, failed_checks: 0, inadequate_checks: 2 },
    } } })
    renderPage()
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent('Not enough checks yet. There is not enough data to tell in: 08:00, 09:00')
    expect(screen.getByTestId('decision-plain')).not.toHaveTextContent('Run:')
    expect(screen.queryByRole('heading', { name: 'Missing evidence' })).not.toBeInTheDocument()
    expect(screen.getByText(/The completed checks could not show whether this plan passes in every period\./)).toBeInTheDocument()
  })

  it.each([
    { failed_periods: ['13:00-14:00'], facts: { failed_checks: 2, validation_checks: 60 }, expected: 'in 13:00-14:00' },
    { failed_periods: [], facts: { failed_checks: 2, validation_checks: 60 }, expected: '2 of 60 checks' },
    { failed_periods: [], facts: null, expected: 'This saved run did not pass. Review' },
  ])('reads selected root periods and check counts without inventing period counts: $expected', async ({ expected, ...fields }) => {
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    getWorkflowMock.mockResolvedValue({ decision_stale: false, decision: { result: {
      ...insufficient, provenance: 'SELECTED', status: 'revise', missing_evidence: [], ...fields,
    } } })
    renderPage()
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent(expected)
  })

  it('renders only persisted evidence returned by the workflow API', async () => {
    getWorkflowMock.mockResolvedValue({
      analysis_id: 7,
      selection: null,
      scenario: null,
      des: null,
      mc: null,
      validation: null,
      decision: {
        id: 5,
        kind: 'workflow_decision',
        status: 'completed',
        params: {},
        result: insufficient,
        created_at: '2026-09-13T00:00:00Z',
        finished_at: '2026-09-13T00:01:00Z',
      },
      decision_stale: false,
    })
    renderPage()
    expect(await screen.findByText(insufficient.headline)).toBeInTheDocument()
    expect(screen.getByText('a completed Scenario Validation run')).toBeInTheDocument()
    // U10 F5: the page asks the spec's question and answers it from the stored fields.
    expect(screen.getByRole('heading', { level: 1, name: 'Should we use this plan?' })).toBeInTheDocument()
    expect(screen.getByTestId('decision-plain')).toHaveTextContent(`Not enough checks yet. Run: ${insufficient.missing_evidence.join('; ')}`)
  })

  it('requests deterministic derivation and renders the server result', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Generate Decision' }))
    await waitFor(() => expect(createDecisionMock).toHaveBeenCalledWith(7))
    expect(await screen.findByText(insufficient.recommendation)).toBeInTheDocument()
  })

  it('warns when newer simulation evidence made the prior Decision stale', async () => {
    getWorkflowMock.mockResolvedValue({
      analysis_id: 7,
      selection: null,
      scenario: null,
      des: null,
      mc: null,
      validation: null,
      decision: null,
      decision_stale: true,
    })
    renderPage()
    expect(await screen.findByText(/prior Decision is stale/)).toBeInTheDocument()
  })

  it('does not present stale persisted evidence as the current Decision', async () => {
    getWorkflowMock.mockResolvedValue({
      analysis_id: 7,
      selection: null,
      scenario: null,
      des: null,
      mc: null,
      validation: null,
      decision: {
        id: 5,
        kind: 'workflow_decision',
        status: 'completed',
        params: {},
        result: insufficient,
        created_at: '2026-09-13T00:00:00Z',
        finished_at: '2026-09-13T00:01:00Z',
      },
      decision_stale: true,
    })
    renderPage()
    expect(await screen.findByText(/prior Decision is stale/)).toBeInTheDocument()
    expect(screen.queryByText(insufficient.headline)).not.toBeInTheDocument()
    expect(screen.getByText('No current Decision')).toBeInTheDocument()
  })

  it('derives a Separate Queue decision through the selected-plan endpoint', async () => {
    const conditional = {
      ...insufficient,
      status: 'conditional',
      headline: 'Consider Scenario "Plan A" conditionally.',
      recommendation: 'All 3 validation checks passed.',
      missing_evidence: [],
    }
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    runSelectedDecisionMock.mockImplementation(async () => {
      getWorkflowMock.mockResolvedValue({
        analysis_id: 7, selection: null, scenario: null, des: null, mc: null, validation: null,
        decision: {
          id: 9, kind: 'workflow_decision', status: 'completed', params: {}, result: conditional,
          created_at: '2026-09-18T00:00:00Z', finished_at: '2026-09-18T00:00:01Z',
        },
        decision_stale: false,
      })
      return { decision: conditional, persisted: true, evidence: {} }
    })
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Generate Decision' }))
    await waitFor(() => expect(runSelectedDecisionMock).toHaveBeenCalledWith(7))
    expect(createDecisionMock).not.toHaveBeenCalled()
    expect(await screen.findByText(conditional.recommendation)).toBeInTheDocument()
  })

  it('says the saving cannot be calculated when today cannot keep up', async () => {
    const overloaded = { ...insufficient, status: 'conditional', headline: 'Consider Scenario "Plan A" conditionally.', missing_evidence: [],
      facts: { validation_intervals: 4, failed_intervals: 0, current_modeled_cost: null, modeled_savings: null, today_overloaded_periods: ['segment_3'] } }
    getWorkflowMock.mockResolvedValue({ analysis_id: 7, selection: null, scenario: null, des: null, mc: null, validation: null,
      decision: { id: 6, kind: 'workflow_decision', status: 'completed', params: {}, result: overloaded,
        created_at: '2026-10-13T00:00:00Z', finished_at: '2026-10-13T00:01:00Z' }, decision_stale: false })
    renderPage()
    expect(await screen.findByTestId('decision-plain')).toHaveTextContent(
      "The plan passed every check, but its cost saving can't be calculated: today's staff can't keep up in segment_3.")
  })

  it('keeps shared analyses on the shared Decision endpoint', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Generate Decision' }))
    await waitFor(() => expect(createDecisionMock).toHaveBeenCalledWith(7))
    expect(runSelectedDecisionMock).not.toHaveBeenCalled()
  })
})

describe('DecisionEndpointPage refusal detail (5d)', () => {
  it('shows the server detail naming the missing dependency instead of a generic error', async () => {
    const detail = 'Evidence references records that no longer exist: dataset #12. Rerun the affected step.'
    createDecisionMock.mockRejectedValue(Object.assign(new Error('Request failed with status code 409'), {
      response: { status: 409, data: { detail } },
    }))
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Generate Decision' }))
    expect(await screen.findByText(detail)).toHaveAttribute('role', 'alert')
    expect(screen.queryByText('The server encountered an error. Please try again.')).not.toBeInTheDocument()
  })
})

describe('DecisionEndpointPage check strip (Phase E)', () => {
  const family = { estimand: 'mean_load', confidence_level: 0.95, family_size: 60, replications: 20, assumptions: [], pass_count: 50, fail_count: 8, insufficient_count: 2 }
  const separateDecision = { ...insufficient, provenance: 'SELECTED', status: 'revise', missing_evidence: [], failed_periods: [],
    facts: { validation_checks: 60, failed_checks: 8 }, load_uncertainty: family, evidence_ids: { selection: 1, des: 10, mc: 11, validation: 12 } }
  const mcRows = (trials: number[]) => trials.map((num_trials, index) => ({ time: '08:00', queue_id: index ? 'b' : 'a', num_trials, failure_threshold: 0.85, failure_rate_cap: 0.05 }))
  const workflowWith = (decision: unknown, stale = false, mc: unknown = null) => ({ analysis_id: 7, selection: null, scenario: null, des: null, mc, validation: null,
    decision: { id: 5, kind: 'workflow_decision', status: 'completed', params: {}, result: decision, created_at: '2026-09-13T00:00:00Z', finished_at: '2026-09-13T00:01:00Z' },
    decision_stale: stale })
  const strip = () => within(screen.getByTestId('check-count-strip')).getAllByRole('definition').map((node) => node.textContent)

  it('shows the decision\'s recorded total and outcome counts, and the trials of its own run', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    getWorkflowMock.mockResolvedValue(workflowWith(separateDecision, false, { id: 11, kind: 'workflow_mc', status: 'completed', params: {}, result: { results: mcRows([2000, 2000]) } }))
    renderPage()
    await screen.findByTestId('check-count-strip')
    expect(strip()).toEqual(['60', '50', '8', '2'])
    expect(screen.getByTestId('check-method-trials')).toHaveTextContent('2,000')
    expect(screen.getByTestId('check-method-rule')).toHaveTextContent('A variation fails when a cashier’s Utilization Rate is above 85%.')
  })

  it('shows Unavailable trials for a run the decision did not use, and Unavailable counts for legacy evidence', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    const legacy = { ...separateDecision, load_uncertainty: undefined }
    getWorkflowMock.mockResolvedValue(workflowWith(legacy, false, { id: 99, kind: 'workflow_mc', status: 'completed', params: {}, result: { results: mcRows([2000, 2000]) } }))
    renderPage()
    await screen.findByTestId('check-count-strip')
    expect(strip()).toEqual(['60', 'Unavailable', 'Unavailable', 'Unavailable'])
    expect(screen.getByTestId('check-method-trials')).toHaveTextContent('Unavailable')
  })

  it('shows no strip for a shared-queue decision or a stale decision, and keeps the stale alert', async () => {
    getWorkflowMock.mockResolvedValue(workflowWith(insufficient))
    const view = renderPage()
    expect(await screen.findByTestId('decision-plain')).toBeInTheDocument()
    expect(document.querySelector('.check-stats')).toBeNull()
    view.unmount()
    getAnalysisMock.mockResolvedValue(analysisWith('separate_queues'))
    getWorkflowMock.mockResolvedValue(workflowWith(separateDecision, true))
    renderPage()
    expect(await screen.findByText(/prior Decision is stale/)).toBeInTheDocument()
    expect(document.querySelector('.check-stats')).toBeNull()
    expect(screen.queryByTestId('check-method-details')).not.toBeInTheDocument()
  })
})

describe('DecisionEndpointPage pilot guidance (owner 2026-11-26)', () => {
  const EN = "The plan held up in Many variations, but the Results check needs more evidence before it can confirm it. Use it as a pilot: record arrivals and waits, and open another cashier if any line's wait in a period goes over your limit."
  const TL = 'Pumasa ang plano sa Many variations, pero kailangan pa ng Results check ng mas maraming ebidensiya bago ito makumpirma. Gamitin ito bilang pilot: itala ang pagdating at paghihintay, at magbukas ng isa pang cashier kapag lumampas sa limit ang hintay sa alinmang linya sa isang period.'
  const family = (fail: number, insufficient: number) => ({ estimand: 'mean_load', confidence_level: 0.95, family_size: 60, replications: 20, assumptions: [], pass_count: 60 - fail - insufficient, fail_count: fail, insufficient_count: insufficient })
  const base = { ...insufficient, provenance: 'SELECTED', missing_evidence: [], inadequate_periods: ['08:00'], selected_load_method: 'selected-load-truncated-hoeffding-v1',
    facts: { validation_checks: 60, failed_checks: 0, inadequate_checks: 60 }, load_uncertainty: family(0, 60), evidence_ids: { selection: 2, des: 4, mc: 6, validation: 7 } }
  const mc = (statuses: string[], id = 6) => ({ id, kind: 'workflow_mc', status: 'completed', params: {}, result: { results: statuses.map((status, index) => ({ time: '08:00', queue_id: String(index), status })) } })
  const workflowWith = (decision: unknown, mcJob: unknown, stale = false) => ({ analysis_id: 7, selection: null, scenario: null, des: null, mc: mcJob, validation: null,
    decision: { id: 8, kind: 'workflow_decision', status: 'completed', params: {}, result: decision, created_at: '', finished_at: '' }, decision_stale: stale })

  async function render(decision: unknown, mcJob: unknown, { separate = true, stale = false, lang = 'en' as 'en' | 'tl' } = {}) {
    getAnalysisMock.mockResolvedValue(analysisWith(separate ? 'separate_queues' : 'shared_queue'))
    getWorkflowMock.mockResolvedValue(workflowWith(decision, mcJob, stale))
    const view = renderWithProviders(<Routes><Route path="/analyses/:analysisId/decision" element={<DecisionEndpointPage />} /></Routes>, { route: '/analyses/7/decision', lang })
    await screen.findByRole('heading', { level: 1 })
    await waitFor(() => expect(getWorkflowMock).toHaveBeenCalled())
    return view
  }

  it('shows the owner guidance beside the unchanged answer when every cited run row passed', async () => {
    await render(base, mc(['PASS', 'PASS']))
    const guidance = await screen.findByTestId('selected-raw-pass-guidance')
    expect(guidance).toHaveTextContent(EN)
    // The existing answer and recommendation are unchanged.
    expect(screen.getByTestId('decision-plain')).toHaveTextContent('Not enough checks yet. There is not enough data to tell in: 08:00')
    expect(screen.getByText(insufficient.recommendation)).toBeInTheDocument()
  })

  it('shows the Tagalog guidance', async () => {
    await render(base, mc(['PASS']), { lang: 'tl' })
    expect(await screen.findByTestId('selected-raw-pass-guidance')).toHaveTextContent(TL)
  })

  it.each([
    ['a revise decision', { ...base, status: 'revise' }, mc(['PASS']), {}],
    ['a conditional decision', { ...base, status: 'conditional' }, mc(['PASS']), {}],
    ['a failed Many variations row', base, mc(['PASS', 'FAIL']), {}],
    ['a run the decision does not cite', base, mc(['PASS'], 99), {}],
    ['missing Many variations rows', base, null, {}],
    ['legacy evidence without the family', { ...base, load_uncertainty: undefined }, mc(['PASS']), {}],
    ['a recorded failed check', { ...base, load_uncertainty: family(1, 59) }, mc(['PASS']), {}],
    ['a shared-queue decision', base, mc(['PASS']), { separate: false }],
    ['a stale decision', base, mc(['PASS']), { stale: true }],
  ] as const)('hides the guidance for %s', async (_name, decision, mcJob, options) => {
    await render(decision, mcJob, options)
    await screen.findByText('stale' in options && options.stale ? /prior Decision is stale/ : insufficient.provenance_warning)
    expect(screen.queryByTestId('selected-raw-pass-guidance')).not.toBeInTheDocument()
  })
})
