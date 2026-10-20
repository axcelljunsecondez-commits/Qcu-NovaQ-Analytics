import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { act, screen, within } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { LAST_ANALYSIS_KEY, rememberLastAnalysis } from '../../lib/lastAnalysis'
import { Sidebar } from './Sidebar'

vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const listAnalysesMock = vi.fn()
vi.mock('../../api/analyses', () => ({
  listAnalyses: (...args: unknown[]) => listAnalysesMock(...args),
}))

function analysis(id: number, archived = false) {
  return {
    id,
    name: `Analysis ${id}`,
    service_type: null,
    location_label: null,
    queue_setup: 'shared',
    setup_status: 'ready',
    archived_at: archived ? '2026-10-01T00:00:00Z' : null,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
  }
}

beforeEach(() => {
  localStorage.clear()
  listAnalysesMock.mockReset()
  listAnalysesMock.mockResolvedValue({ analyses: [analysis(7), analysis(9, true)] })
})

afterEach(() => vi.restoreAllMocks())

async function navLinks() {
  const nav = await screen.findByRole('navigation', { name: 'Global navigation' })
  await screen.findByRole('button', { name: 'Account menu for a@b.c' })
  return nav
}

describe('Sidebar global navigation (spec §7.3)', () => {
  it('shows the four groups and five destinations in order', async () => {
    renderWithProviders(<Sidebar />, { route: '/analyses' })
    const nav = await navLinks()
    expect(within(nav).getAllByText(/^(Workspace|Insights|Simulation|Tools)$/).map((node) => node.textContent))
      .toEqual(['Workspace', 'Insights', 'Simulation', 'Tools'])
    expect(within(nav).getAllByRole('link').map((link) => link.textContent))
      .toEqual(['My analyses', 'Analysis results', 'Reports', 'Queue simulation', 'Quick calculator'])
  })

  it('moves Help, Settings, language and Log out out of the link list into the account menu', async () => {
    renderWithProviders(<Sidebar />, { route: '/analyses' })
    const nav = await navLinks()
    for (const name of ['Help', 'Get help', 'Settings', 'Account', 'Admin', 'Datasets', 'Dashboard']) {
      expect(within(nav).queryByRole('link', { name })).not.toBeInTheDocument()
    }
    expect(screen.queryByRole('button', { name: 'Logout' })).not.toBeInTheDocument()
    expect(screen.queryByRole('group', { name: 'Language' })).not.toBeInTheDocument()
  })

  it('opens Insights and Simulation items on the last-used analysis when it is still listed', async () => {
    localStorage.setItem(LAST_ANALYSIS_KEY, '7')
    renderWithProviders(<Sidebar />, { route: '/analyses' })
    await navLinks()
    expect(await screen.findByRole('link', { name: 'Analysis results' })).toHaveAttribute('href', '/results?analysis=7')
    expect(screen.getByRole('link', { name: 'Reports' })).toHaveAttribute('href', '/reports?analysis=7')
    expect(screen.getByRole('link', { name: 'Queue simulation' })).toHaveAttribute('href', '/simulation/results?analysis=7')
    expect(screen.getByRole('link', { name: 'Quick calculator' })).toHaveAttribute('href', '/tools/calculator')
  })

  it('follows the analysis the user opens without waiting for another navigation', async () => {
    renderWithProviders(<Sidebar />, { route: '/analyses' })
    await navLinks()
    await vi.waitFor(() => expect(listAnalysesMock).toHaveBeenCalled())
    expect(screen.getByRole('link', { name: 'Analysis results' })).toHaveAttribute('href', '/results')
    act(() => rememberLastAnalysis(7))
    expect(screen.getByRole('link', { name: 'Analysis results' })).toHaveAttribute('href', '/results?analysis=7')
    expect(localStorage.getItem(LAST_ANALYSIS_KEY)).toBe('7')
  })

  it.each([
    ['an archived analysis', '9'],
    ['an analysis that is not listed', '42'],
    ['a malformed value', 'abc'],
  ])('opens the Results picker for %s', async (_label, stored) => {
    localStorage.setItem(LAST_ANALYSIS_KEY, stored)
    renderWithProviders(<Sidebar />, { route: '/analyses' })
    await navLinks()
    await vi.waitFor(() => expect(listAnalysesMock).toHaveBeenCalled())
    expect(screen.getByRole('link', { name: 'Analysis results' })).toHaveAttribute('href', '/results')
  })

  it('opens the Simulation picker when storage cannot be read', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    renderWithProviders(<Sidebar />, { route: '/analyses' })
    await navLinks()
    expect(screen.getByRole('link', { name: 'Queue simulation' })).toHaveAttribute('href', '/simulation/results')
  })

  it('keeps an explicit translated name on every collapsed link', async () => {
    renderWithProviders(<Sidebar collapsed onToggleCollapsed={() => undefined} />, { route: '/analyses' })
    const nav = await navLinks()
    for (const name of ['My analyses', 'Analysis results', 'Reports', 'Queue simulation', 'Quick calculator']) {
      expect(within(nav).getByRole('link', { name })).toHaveAttribute('aria-label', name)
    }
  })

  it('marks exactly one destination as the current page', async () => {
    localStorage.setItem(LAST_ANALYSIS_KEY, '7')
    renderWithProviders(<Sidebar />, { route: '/simulation/replay?analysis=7' })
    const nav = await navLinks()
    const current = within(nav).getAllByRole('link').filter((link) => link.getAttribute('aria-current') === 'page')
    expect(current.map((link) => link.textContent)).toEqual(['Queue simulation'])
  })

  it.each([
    ['/analyses/7/setup', 'My analyses'],
    ['/analyses/7/data', 'My analyses'],
    ['/results?analysis=7', 'Analysis results'],
    ['/results?analysis=7&file=12&period=08%3A00', 'Analysis results'],
    ['/analyses/7/reports', 'Reports'],
    ['/analyses/7/decision', 'Queue simulation'],
    ['/simulation/checks?analysis=7&plan=current', 'Queue simulation'],
    ['/tools/calculator', 'Quick calculator'],
  ])('highlights the right destination on %s', async (route, name) => {
    renderWithProviders(<Sidebar />, { route })
    await navLinks()
    expect(screen.getByRole('link', { name })).toHaveAttribute('aria-current', 'page')
  })

  it('offers the hide-sidebar icon only when the layout can collapse it', async () => {
    const { unmount } = renderWithProviders(<Sidebar />, { route: '/analyses' })
    await navLinks()
    expect(screen.queryByRole('button', { name: 'Hide sidebar' })).not.toBeInTheDocument()
    unmount()
    renderWithProviders(<Sidebar onToggleCollapsed={() => undefined} />, { route: '/analyses' })
    await navLinks()
    const toggle = screen.getByRole('button', { name: 'Hide sidebar' })
    expect(toggle).toHaveAttribute('aria-expanded', 'true')
    expect(toggle).not.toHaveTextContent(/collapse/i)
  })
})
