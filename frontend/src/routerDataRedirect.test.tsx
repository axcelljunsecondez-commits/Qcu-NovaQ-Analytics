import { describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { createAppRouter } from './router'
import { makeQueryClient, testI18n } from './test/test-utils'

const setup = {
  queue_structure: 'shared_queue', fixed_server_count: null, staffing_varies_by_period: false, capacity_mode: 'unknown',
  total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null, segments: [],
  separate_queue_closure_policy: 'drain_existing', queue_ids: [], breaks: [],
}
const project = { id: 7, name: 'NovaMart', service_type: null, location_label: null, queue_setup: setup,
  setup_status: 'ready', archived_at: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' }

vi.mock('./api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' } })),
  login: vi.fn(),
  logout: vi.fn(),
}))
vi.mock('./api/analyses', () => ({
  getAnalysis: vi.fn(async () => ({ analysis: project })),
  listAnalyses: vi.fn(async () => ({ analyses: [project] })),
  listAnalysisDatasets: vi.fn(async () => ({ datasets: [] })),
  getAnalysisCurrent: vi.fn(),
  patchAnalysis: vi.fn(),
  uploadAnalysisDataset: vi.fn(),
  previewAnalysisDataset: vi.fn(),
  downloadSetupWorkbook: vi.fn(),
}))
vi.mock('./api/templates', () => ({
  getTemplateGuide: vi.fn(),
  downloadTemplate: vi.fn(),
}))

function renderAt(path: string) {
  const router = createMemoryRouter(createAppRouter().routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={makeQueryClient()}>
      <I18nextProvider i18n={testI18n()}>
        <RouterProvider router={router} />
      </I18nextProvider>
    </QueryClientProvider>,
  )
  return router
}

describe('Data and setup address (spec §5)', () => {
  it('redirects the old Setup address and keeps the query and hash', async () => {
    const router = renderAt('/analyses/7/setup?from=email#upload')
    await waitFor(() => expect(router.state.location.pathname).toBe('/analyses/7/data'))
    expect(router.state.location.search).toBe('?from=email')
    expect(router.state.location.hash).toBe('#upload')
    expect(await screen.findByRole('heading', { level: 1, name: 'Data and setup' })).toBeInTheDocument()
  })

  it('opens Data and setup for a bare analysis address', async () => {
    const router = renderAt('/analyses/7')
    await waitFor(() => expect(router.state.location.pathname).toBe('/analyses/7/data'))
  })
})
