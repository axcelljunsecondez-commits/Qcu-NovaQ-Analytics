import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
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

  it('keeps shared analyses on the shared Decision endpoint', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Generate Decision' }))
    await waitFor(() => expect(createDecisionMock).toHaveBeenCalledWith(7))
    expect(runSelectedDecisionMock).not.toHaveBeenCalled()
  })
})
