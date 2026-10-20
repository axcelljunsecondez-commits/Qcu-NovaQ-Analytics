import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { useLocation } from 'react-router-dom'
import { renderWithProviders } from '../../test/test-utils'
import { AnalysisEntry } from './AnalysisEntry'
import { LAST_ANALYSIS_KEY } from '../../lib/lastAnalysis'
import type { AnalysisDestination } from '../../lib/analysisDestination'

const listMock = vi.fn()
vi.mock('../../api/analyses', () => ({ listAnalyses: (...args: unknown[]) => listMock(...args) }))
vi.mock('../../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))

const saved = { id: 7, name: 'Saved checkout', location_label: 'North branch', service_type: null, archived_at: null }
function Address() { const location = useLocation(); return <div data-testid="address">{location.pathname}{location.search}</div> }
function renderEntry(destination: AnalysisDestination = 'results', route = `/${destination}`) {
  return renderWithProviders(<><AnalysisEntry destination={destination} /><Address /></>, { route })
}
beforeEach(() => {
  listMock.mockReset().mockResolvedValue({ analyses: [saved, { ...saved, id: 9, name: 'Archived', archived_at: '2026-10-01' }] })
})
afterEach(() => vi.restoreAllMocks())

describe('authenticated analysis entry', () => {
  it.each(['results', 'reports', 'simulation/results', 'simulation/replay', 'simulation/checks'] as const)('keeps the %s destination when opening a saved analysis', async (destination) => {
    const user = userEvent.setup()
    renderEntry(destination)
    expect(await screen.findByRole('link', { name: 'Open Saved checkout' })).toHaveAttribute('href', `/${destination}?analysis=7`)
    expect(screen.queryByText('Archived')).not.toBeInTheDocument()
    await user.click(screen.getByRole('link', { name: 'Open Saved checkout' }))
    expect(screen.getByTestId('address')).toHaveTextContent(`/${destination}?analysis=7`)
  })

  it.each(['9', '42', 'abc', '-1', '1.5'])('shows the picker for an invalid, foreign or archived hint %s', async (stored) => {
    localStorage.setItem(LAST_ANALYSIS_KEY, stored)
    renderEntry()
    expect(await screen.findByRole('link', { name: 'Open Saved checkout' })).toBeInTheDocument()
    expect(screen.getByTestId('address')).toHaveTextContent('/results')
  })

  it('opens a valid last-used analysis without asking the user to create one', async () => {
    localStorage.setItem(LAST_ANALYSIS_KEY, '7')
    renderEntry('reports')
    await waitFor(() => expect(screen.getByTestId('address')).toHaveTextContent('/reports?analysis=7'))
  })

  it('allows an explicit choice even when a valid last-used analysis exists', async () => {
    localStorage.setItem(LAST_ANALYSIS_KEY, '7')
    renderEntry('results', '/results?choose=1')
    expect(await screen.findByRole('link', { name: 'Open Saved checkout' })).toBeInTheDocument()
  })

  it('does not silently replace a malformed explicit analysis with the stored analysis', async () => {
    localStorage.setItem(LAST_ANALYSIS_KEY, '7')
    renderEntry('results', '/results?analysis=bad')
    expect(await screen.findByRole('link', { name: 'Open Saved checkout' })).toBeInTheDocument()
    expect(screen.getByTestId('address')).toHaveTextContent('/results?analysis=bad')
  })

  it('offers the intended creation continuation for an empty account', async () => {
    listMock.mockResolvedValue({ analyses: [] })
    renderEntry('simulation/replay')
    expect(await screen.findByText('You have no analyses yet.')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'New Analysis' })).toHaveAttribute('href', '/analyses/new?continue=simulation%2Freplay')
  })

  it('shows a request error rather than claiming the account has no records, and can retry', async () => {
    const user = userEvent.setup()
    listMock.mockRejectedValueOnce(new Error('offline'))
    renderEntry()
    expect(await screen.findByRole('alert')).toBeInTheDocument()
    expect(screen.queryByText('You have no analyses yet.')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Try loading analyses again' }))
    expect(await screen.findByRole('link', { name: 'Open Saved checkout' })).toBeInTheDocument()
  })

  it('shows loading separately from an empty account', () => {
    listMock.mockImplementation(() => new Promise(() => undefined))
    renderEntry()
    expect(screen.getByRole('status')).toHaveTextContent('Loading')
    expect(screen.queryByText('You have no analyses yet.')).not.toBeInTheDocument()
  })

  it('finds an existing analysis by location and explains a search with no match', async () => {
    const user = userEvent.setup()
    renderEntry()
    const search = await screen.findByLabelText('Search analyses')
    await user.type(search, 'North')
    expect(screen.getByRole('link', { name: 'Open Saved checkout' })).toBeInTheDocument()
    await user.clear(search)
    await user.type(search, 'Missing')
    expect(screen.queryByRole('link', { name: 'Open Saved checkout' })).not.toBeInTheDocument()
    expect(screen.queryByText('You have no analyses yet.')).not.toBeInTheDocument()
  })

  it('works when browser storage is unavailable', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
    renderEntry()
    expect(await screen.findByRole('link', { name: 'Open Saved checkout' })).toBeInTheDocument()
  })
})
