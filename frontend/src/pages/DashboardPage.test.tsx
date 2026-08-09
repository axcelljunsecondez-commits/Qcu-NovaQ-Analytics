import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import { renderWithProviders } from '../test/test-utils'
import { DashboardPage } from './DashboardPage'

const listDatasetsMock = vi.fn()

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
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
  row_count: 4,
  validation: { ok: true, message: 'Input data is valid.' },
  created_at: '2026-08-01T10:00:00Z',
  normalized: null,
}

beforeEach(() => {
  listDatasetsMock.mockReset()
})

describe('DashboardPage', () => {
  it('shows loading state while datasets are fetched', () => {
    listDatasetsMock.mockReturnValue(new Promise(() => {}))
    renderWithProviders(<DashboardPage />, { route: '/dashboard' })
    expect(screen.getByText('Loading…')).toBeInTheDocument()
  })

  it('renders dataset stats after load', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
    renderWithProviders(<DashboardPage />, { route: '/dashboard' })
    await waitFor(() => {
      expect(screen.getByText('sample')).toBeInTheDocument()
    })
    expect(screen.getByText('1')).toBeInTheDocument()
    expect(screen.getByText('a@b.c')).toBeInTheDocument()
  })

  it('renders empty state when no datasets exist', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [] })
    renderWithProviders(<DashboardPage />, { route: '/dashboard' })
    expect(
      await screen.findByText('No datasets yet. Upload your first queue data file to get started.'),
    ).toBeInTheDocument()
  })

  it('renders workflow quick-action links', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [] })
    renderWithProviders(<DashboardPage />, { route: '/dashboard' })
    for (const label of ['Datasets', 'Analysis', 'Optimize', 'Simulate', 'Compare']) {
      const link = await screen.findAllByRole('link', { name: label })
      expect(link.length).toBeGreaterThan(0)
    }
  })
})
