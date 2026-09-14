import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { AnalysisSetupPage } from './AnalysisSetupPage'
import { GuidedSetupPage } from './GuidedSetupPage'

const getAnalysisMock = vi.fn()
const patchAnalysisMock = vi.fn()
const listAnalysisDatasetsMock = vi.fn()
const getAnalysisCurrentMock = vi.fn()

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: (...args: unknown[]) => patchAnalysisMock(...args),
  listAnalysisDatasets: (...args: unknown[]) => listAnalysisDatasetsMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getAnalysisCurrentMock(...args),
  uploadAnalysisDataset: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const unknownSetup = {
  queue_structure: 'unknown',
  fixed_server_count: null,
  staffing_varies_by_period: false,
  capacity_mode: 'unknown',
  total_system_capacity: null,
  abandonment_mode: 'unknown',
  patience_rate_per_hour: null,
}

const analysis = {
  id: 7,
  name: 'Unanswered setup',
  service_type: null,
  location_label: null,
  queue_setup: unknownSetup,
  setup_status: 'incomplete',
  archived_at: null,
  created_at: '2026-09-13T00:00:00Z',
  updated_at: '2026-09-13T00:00:00Z',
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue({ analysis })
  patchAnalysisMock.mockReset().mockResolvedValue({ analysis })
  listAnalysisDatasetsMock.mockReset().mockResolvedValue({ datasets: [] })
  getAnalysisCurrentMock.mockReset()
})

describe('setup semantic contracts', () => {
  it('submits untouched canonical setup as unknown and null rather than analytical defaults', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
      </Routes>,
      { route: '/analyses/7/setup' },
    )

    expect(await screen.findByLabelText('Queue structure')).toHaveValue('unknown')
    expect(screen.getByLabelText('Capacity mode')).toHaveValue('unknown')
    expect(screen.getByLabelText('Abandonment')).toHaveValue('unknown')
    expect(screen.getByLabelText('Fixed server count')).toHaveValue(null)

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: unknownSetup,
    }))
  })

  it('redirects the legacy Guided Setup route to canonical Setup without persisting a mapping', async () => {
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/guided" element={<GuidedSetupPage />} />
        <Route path="/analyses/:analysisId/setup" element={<div>Canonical setup</div>} />
      </Routes>,
      { route: '/analyses/7/guided' },
    )

    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('rejects a zero patience rate locally when abandonment modeling is selected', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, abandonment_mode: 'modeled', patience_rate_per_hour: 0 } } })
    const user = userEvent.setup()
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    expect(await screen.findByLabelText('Patience rate per hour (theta)')).toHaveValue(0)
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Patience rate must be greater than zero')
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })
})
