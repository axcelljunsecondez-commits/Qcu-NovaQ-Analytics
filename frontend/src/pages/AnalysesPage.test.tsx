import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
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
    expect(await screen.findByText('You have no analyses yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'How to start an analysis' })).toHaveAttribute('href', '/help')
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
      '/analyses/7/data',
    )
    await user.click(screen.getByRole('button', { name: 'Archive' }))
    expect(archiveMock).not.toHaveBeenCalled()
    const dialog = screen.getByRole('alertdialog', { name: 'Archive “North checkout”?' })
    expect(dialog).toHaveTextContent('cannot take new uploads')
    await user.click(within(dialog).getByRole('button', { name: 'Archive' }))
    expect(archiveMock.mock.calls[0][0]).toBe(7)
  })

  it('offers guided structure choice for unknown-structure analyses', async () => {
    listMock.mockResolvedValue({ analyses: [{ ...analysis, queue_setup: { ...analysis.queue_setup, queue_structure: 'unknown' } }] })
    renderWithProviders(<AnalysesPage />, { route: '/analyses' })
    expect(await screen.findByText('North checkout')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Choose queue structure' })).toHaveAttribute(
      'href',
      '/analyses/7/guided-setup',
    )
  })

  it('hides guided structure choice once structure is known', async () => {
    listMock.mockResolvedValue({ analyses: [analysis] })
    renderWithProviders(<AnalysesPage />, { route: '/analyses' })
    expect(await screen.findByText('North checkout')).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Choose queue structure' })).not.toBeInTheDocument()
  })

  it('badges each analysis with its queue structure', async () => {
    listMock.mockResolvedValue({ analyses: [
      analysis,
      { ...analysis, id: 8, name: 'South lines', queue_setup: { ...analysis.queue_setup, queue_structure: 'separate_queues' } },
    ] })
    renderWithProviders(<AnalysesPage />, { route: '/analyses' })
    expect(await screen.findByText('North checkout')).toBeInTheDocument()
    const badges = screen.getAllByTestId('analysis-structure-badge')
    expect(badges.map((badge) => badge.textContent)).toEqual(["Single Line-Queue for Multiple Counters", "Separate Line-Queue per Counter"])
  })

  it('filters analyses by queue structure', async () => {
    const user = userEvent.setup()
    listMock.mockResolvedValue({ analyses: [
      analysis,
      { ...analysis, id: 8, name: 'South lines', queue_setup: { ...analysis.queue_setup, queue_structure: 'separate_queues' } },
    ] })
    renderWithProviders(<AnalysesPage />, { route: '/analyses' })
    expect(await screen.findByText('North checkout')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Separate lines' }))
    expect(screen.queryByText('North checkout')).not.toBeInTheDocument()
    expect(screen.getByText('South lines')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'One shared line' }))
    expect(screen.getByText('North checkout')).toBeInTheDocument()
    expect(screen.queryByText('South lines')).not.toBeInTheDocument()
  })

  it('initializes the filter from the sidebar structure link', async () => {
    listMock.mockResolvedValue({ analyses: [
      analysis,
      { ...analysis, id: 8, name: 'South lines', queue_setup: { ...analysis.queue_setup, queue_structure: 'separate_queues' } },
    ] })
    renderWithProviders(<AnalysesPage />, { route: '/analyses?structure=separate_queues' })
    expect(await screen.findByText('South lines')).toBeInTheDocument()
    expect(screen.queryByText('North checkout')).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Separate lines' })).toHaveAttribute('aria-pressed', 'true')
  })
})
