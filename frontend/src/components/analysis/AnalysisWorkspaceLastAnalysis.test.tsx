import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../../test/test-utils'
import { LAST_ANALYSIS_KEY } from '../../lib/lastAnalysis'
import { AnalysisWorkspace } from './AnalysisWorkspace'

const getAnalysisMock = vi.fn()
vi.mock('../../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  listAnalyses: vi.fn(async () => ({ analyses: [] })),
}))
vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

const project = {
  id: 7,
  name: 'Store A',
  service_type: null,
  location_label: null,
  queue_setup: 'shared',
  setup_status: 'ready',
  archived_at: null,
  created_at: '2026-10-01T00:00:00Z',
  updated_at: '2026-10-01T00:00:00Z',
}

function renderWorkspace(route: string) {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId" element={<AnalysisWorkspace />}>
        <Route path="setup" element={<p>Setup body</p>} />
      </Route>
    </Routes>,
    { route },
  )
}

beforeEach(() => {
  localStorage.clear()
  getAnalysisMock.mockReset()
})

describe('AnalysisWorkspace last-used analysis (spec §7.3)', () => {
  it('remembers an analysis once it has loaded', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: project })
    renderWorkspace('/analyses/7/setup')
    expect(await screen.findByText('Setup body')).toBeInTheDocument()
    await waitFor(() => expect(localStorage.getItem(LAST_ANALYSIS_KEY)).toBe('7'))
  })

  it('does not remember an analysis that failed to load', async () => {
    getAnalysisMock.mockRejectedValue(new Error('not found'))
    renderWorkspace('/analyses/8/setup')
    await waitFor(() => expect(getAnalysisMock).toHaveBeenCalled())
    await screen.findByRole('alert')
    expect(localStorage.getItem(LAST_ANALYSIS_KEY)).toBeNull()
  })
})
