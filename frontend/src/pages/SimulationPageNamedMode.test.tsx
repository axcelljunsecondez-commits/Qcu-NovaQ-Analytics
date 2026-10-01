import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes, useLocation } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { SimulationPage } from './SimulationPage'
import fixture from '../test/fixtures/sharedNamed.json'

// Named Shared Queue mode on the Simulate page (spec 2026-09-30 §9.1, §16 item 4). The legacy
// page's own tests stay in SimulationPage.test.tsx, unchanged.

const getWorkflowMock = vi.fn()
const getAnalysisMock = vi.fn()
const contractMock = vi.fn()

vi.mock('../api/workflow', () => ({
  getWorkflow: (...args: unknown[]) => getWorkflowMock(...args),
  runWorkflowDes: vi.fn(),
  runWorkflowDesCurrent: vi.fn(),
  runWorkflowMc: vi.fn(),
  runWorkflowMcCurrent: vi.fn(),
  runWorkflowValidation: vi.fn(),
  runWorkflowValidationCurrent: vi.fn(),
  runSelectedDes: vi.fn(),
  runSelectedMc: vi.fn(),
  runSelectedValidation: vi.fn(),
  runSelectedDecision: vi.fn(),
}))
vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  getAnalysisCurrent: vi.fn(async () => ({ dataset: { id: 9 }, rows: [], kpis: {}, explanations: [] })),
  listAnalysisDatasets: vi.fn(async () => ({ datasets: [] })),
}))
vi.mock('../api/sharedNamed', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../api/sharedNamed')>()),
  getNamedContract: (...args: unknown[]) => contractMock(...args),
  listNamedRuns: vi.fn(async () => ({ runs: [] })),
}))
vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' } })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

function workflow(overrides: Record<string, unknown> = {}) {
  return {
    analysis_id: 7,
    selection: null,
    scenario: { id: 3, name: 'Plan A', dataset_id: 2, provenance: 'verified_snapshot' },
    des: null,
    mc: null,
    validation: null,
    decision: null,
    decision_stale: false,
    ...overrides,
  }
}

function setStructure(queueStructure: string) {
  getAnalysisMock.mockResolvedValue({ analysis: { id: 7, queue_setup: { queue_structure: queueStructure } } })
}

let search = ''
function LocationProbe() {
  search = useLocation().search
  return null
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId/simulate" element={<><SimulationPage /><LocationProbe /></>} />
    </Routes>,
    { route },
  )
}

beforeEach(() => {
  getWorkflowMock.mockReset().mockResolvedValue(workflow())
  getAnalysisMock.mockReset()
  contractMock.mockReset().mockResolvedValue(fixture.contract)
  setStructure('shared_queue')
})

describe('Simulate page mode', () => {
  it('keeps the legacy page when no mode is chosen, with the switch on legacy', async () => {
    renderAt('/analyses/7/simulate')
    expect(await screen.findByRole('heading', { name: 'Simulation' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Legacy shared queue simulation' })).toBeChecked()
    expect(screen.getByRole('radio', { name: 'Named Shared Queue simulation' })).not.toBeChecked()
    expect(screen.queryByTestId('named-simulation')).toBeNull()
    expect(contractMock).not.toHaveBeenCalled()
  })

  it('renders the named view for ?mode=named without a Compare selection', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
    renderAt('/analyses/7/simulate?mode=named')
    expect(await screen.findByTestId('named-simulation')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Named Shared Queue simulation' })).toBeInTheDocument()
    expect(screen.queryByText(/select a scenario/i)).toBeNull()
    expect(screen.getByRole('radio', { name: 'Named Shared Queue simulation' })).toBeChecked()
  })

  it('offers the switch on the select-a-scenario screen and switches modes through the URL', async () => {
    getWorkflowMock.mockResolvedValue(workflow({ scenario: null, selection: null }))
    renderAt('/analyses/7/simulate')
    await userEvent.click(await screen.findByRole('radio', { name: 'Named Shared Queue simulation' }))
    expect(await screen.findByTestId('named-simulation')).toBeInTheDocument()
    expect(search).toBe('?mode=named')
    await userEvent.click(screen.getByRole('radio', { name: 'Legacy shared queue simulation' }))
    await waitFor(() => expect(screen.queryByTestId('named-simulation')).toBeNull())
    expect(search).toBe('')
  })

  it.each(['separate_queues', 'single_server', 'unknown'])('ignores ?mode=named and shows no switch for %s', async (structure) => {
    setStructure(structure)
    renderAt('/analyses/7/simulate?mode=named')
    expect(await screen.findByRole('heading', { level: 1, name: 'Simulation' })).toBeInTheDocument()
    expect(screen.queryByTestId('simulation-mode-switch')).toBeNull()
    expect(screen.queryByTestId('named-simulation')).toBeNull()
    expect(contractMock).not.toHaveBeenCalled()
  })
})
