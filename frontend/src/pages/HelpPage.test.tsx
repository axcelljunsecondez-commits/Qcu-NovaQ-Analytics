import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Outlet, Route, Routes } from 'react-router-dom'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'
import { HelpShell } from '../components/layout/HelpShell'
import { HELP_GUIDES } from '../lib/helpGuides'
import { renderWithProviders } from '../test/test-utils'
import { HelpPage } from './HelpPage'

const meMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(async () => ({ user: null })),
  logout: vi.fn(async () => ({})),
}))

vi.mock('../components/layout/AppLayout', () => ({
  AppLayout: () => <div data-testid="app-layout"><Outlet /></div>,
}))

beforeEach(() => {
  meMock.mockReset()
  meMock.mockRejectedValue(Object.assign(new Error('Not signed in'), { status: 401 }))
  Element.prototype.scrollIntoView = vi.fn()
})

function renderHelp(route: string) {
  return renderWithProviders(
    <Routes>
      <Route element={<HelpShell />}>
        <Route path="/help" element={<HelpPage />} />
        <Route path="/help/:topic" element={<HelpPage />} />
      </Route>
      <Route path="/" element={<div>home-marker</div>} />
    </Routes>,
    { route },
  )
}

describe('Help center (plan U8)', () => {
  it('lists every guide and is readable without signing in', async () => {
    renderHelp('/help')
    const guides = await screen.findByRole('region', { name: 'Guides' })
    expect(within(guides).getAllByRole('link').map((link) => link.textContent)).toEqual([
      'Starting an analysis', 'Adding your data', 'Reading results', 'Comparing plans', 'Queue simulation',
      'Checks and decision', 'Downloads', 'Problems'])
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    expect(screen.queryByTestId('app-layout')).not.toBeInTheDocument()
  })

  it('shows Help inside the app when signed in', async () => {
    meMock.mockResolvedValue({ user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' } })
    renderHelp('/help')
    expect(await screen.findByTestId('app-layout')).toBeInTheDocument()
    expect(screen.getByRole('heading', { level: 1, name: 'Help' })).toBeInTheDocument()
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument()
  })

  it('finds sections by every word of the search and links to them', async () => {
    const user = userEvent.setup()
    renderHelp('/help')
    await user.type(await screen.findByLabelText('Find help'), 'closing time')
    const results = screen.getByRole('list', { name: 'Search results' })
    expect(within(results).getByRole('link', { name: 'Queue simulation: Closing time' })).toHaveAttribute('href', '/help/simulation#closing')
    await user.clear(screen.getByLabelText('Find help'))
    await user.type(screen.getByLabelText('Find help'), 'review only')
    expect(within(screen.getByRole('list', { name: 'Search results' })).getByRole('link', {
      name: 'Adding your data: Planning file or review-only file' })).toHaveAttribute('href', '/help/data#purpose')
    await user.clear(screen.getByLabelText('Find help'))
    await user.type(screen.getByLabelText('Find help'), 'closing zebra')
    expect(screen.getByRole('status')).toHaveTextContent('No guide mentions all of these words.')
    await user.clear(screen.getByLabelText('Find help'))
    await user.type(screen.getByLabelText('Find help'), 'exponential')  // in a section's text, not its title
    expect(within(screen.getByRole('list', { name: 'Search results' })).getAllByRole('link').map((link) => link.textContent))
      .toEqual(['Queue simulation: Service times'])
  })

  it('opens a guide with what to do, why, the next step and its sections, at the linked section', async () => {
    renderHelp('/help/simulation#closing')
    expect(await screen.findByRole('heading', { level: 1, name: 'Queue simulation' })).toBeInTheDocument()
    expect(screen.getByText('What to do')).toBeInTheDocument()
    expect(screen.getByText('Open Queue simulation, choose Current or Suggested plan, and run it.')).toBeInTheDocument()
    expect(screen.getByText('Next step')).toBeInTheDocument()
    const closing = screen.getByRole('region', { name: 'Closing time' })
    expect(closing).toHaveAttribute('id', 'closing')
    expect(Element.prototype.scrollIntoView).toHaveBeenCalled()
    expect(screen.getByRole('link', { name: 'All guides' })).toHaveAttribute('href', '/help')
  })

  it('sends an unknown guide back to the list', async () => {
    renderHelp('/help/nonsense')
    expect(await screen.findByRole('region', { name: 'Guides' })).toBeInTheDocument()
  })

  it('has every guide text in English and Tagalog', () => {
    const keys = HELP_GUIDES.flatMap(({ topic, sections }) => [
      ...['title', 'action', 'purpose', 'next'].map((part) => `help.guide.${topic}.${part}`),
      ...sections.flatMap((section) => [`help.guide.${topic}.${section}.title`, `help.guide.${topic}.${section}.body`]),
    ])
    const english = en as Record<string, string>
    const tagalog = tl as Record<string, string>
    expect(keys.filter((key) => !english[key]?.trim())).toEqual([])
    expect(keys.filter((key) => !tagalog[key]?.trim())).toEqual([])
  })
})
