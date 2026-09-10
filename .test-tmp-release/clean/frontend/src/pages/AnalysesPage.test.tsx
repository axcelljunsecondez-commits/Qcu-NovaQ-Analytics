import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { AnalysesPage } from './AnalysesPage'

const listMock = vi.fn()
const archiveMock = vi.fn()

vi.mock('../api/analyses', () => ({
  listAnalyses: (...args: unknown[]) => listMock(...args),
  archiveAnalysis: (...args: unknown[]) => archiveMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

const analysis = {
  id: 7,
  name: 'North checkout',
  service_type: 'checkout',
  location_label: 'North',
  queue_setup: {
    queue_structure: 'shared_queue',
    fixed_server_count: 2,
    staffing_varies_by_period: false,
    capacity_mode: 'unlimited',
    total_system_capacity: null,
    abandonment_mode: 'not_modeled',
    patience_rate_per_hour: null,
  },
  setup_status: 'ready',
  archived_at: null,
  created_at: '2026-09-08T00:00:00Z',
  updated_at: '2026-09-08T00:00:00Z',
}

beforeEach(() => {
  listMock.mockReset()
  archiveMock.mockReset()
  archiveMock.mockResolvedValue({ analysis: { ...analysis, archived_at: '2026-09-08T01:00:00Z' } })
})

describe('AnalysesPage', () => {
  it('shows the guided empty state', async () => {
    listMock.mockResolvedValue({ analyses: [] })
    renderWithProviders(<AnalysesPage />, { route: '/analyses' })
    expect(await screen.findByText('You do not have any Analyses yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Create your first Analysis' })).toHaveAttribute(
      'href',
      '/analyses/new',
    )
  })

  it('opens and archives an owned Analysis', async () => {
    listMock.mockResolvedValue({ analyses: [analysis] })
    const user = userEvent.setup()
    renderWithProviders(<AnalysesPage />, { route: '/analyses' })
    expect(await screen.findByText('North checkout')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Open' })).toHaveAttribute(
      'href',
      '/analyses/7/setup',
    )
    await user.click(screen.getByRole('button', { name: 'Archive' }))
    expect(archiveMock.mock.calls[0][0]).toBe(7)
  })
})
