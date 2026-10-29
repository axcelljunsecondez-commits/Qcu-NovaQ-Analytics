import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { HomePage } from './HomePage'
import { HelpPage } from './HelpPage'

vi.mock('../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
  window.scrollTo = vi.fn()
})

describe('Approved homepage learning behavior', () => {
  it('opens How it works without hash navigation and loops its three accessible steps', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HomePage />)
    const header = screen.getByRole('banner')
    const headerButton = within(header).getByRole('button', { name: "How It Works" })
    expect(headerButton).not.toHaveAttribute('href')
    expect(headerButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('heading', { name: "Add your Records" })).not.toBeInTheDocument()
    await user.click(headerButton)
    expect(headerButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('heading', { name: "Add your Records" })).toBeInTheDocument()
    const next = screen.getByRole('button', { name: 'Next: How It Works' })
    await user.click(next);expect(screen.getByRole('heading', { name: "See Suggested Plans" })).toBeInTheDocument()
    await user.click(next);expect(screen.getByRole('heading', { name: "Watch the Simulation" })).toBeInTheDocument()
    await user.click(next);expect(screen.getByRole('heading', { name: "Add your Records" })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Previous: How It Works' }))
    expect(screen.getByRole('heading', { name: "Watch the Simulation" })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: "How It Works", description: 'From your records to a service plan' }))
    expect(document.getElementById('home-how-it-works-panel')).toHaveAttribute('inert')
    expect(window.scrollTo).not.toHaveBeenCalled()
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
  })

  it('places one collapsible side-by-side queue comparison below both spotlight columns without pagination', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HomePage />)
    const spotlight = document.querySelector('.home-spotlight')!
    const comparison = document.querySelector('.home-queue-comparison')!
    expect(spotlight.children).toHaveLength(3)
    expect(spotlight.lastElementChild).toBe(comparison)
    const trigger = screen.getByRole('button', { name: 'Queue types' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await user.click(trigger)
    expect(screen.getByRole('img', { name: /three separate lines/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /one shared line/ })).toBeInTheDocument()
    expect(comparison.querySelectorAll('article')).toHaveLength(2)
    expect(within(comparison as HTMLElement).queryByRole('button', { name: /Next|Previous/ })).not.toBeInTheDocument()
    await user.click(trigger)
    expect(document.getElementById('home-queue-types-panel')).toHaveAttribute('inert')
    expect(screen.getAllByRole('link', { name: "Start an Analysis" })).toHaveLength(1)
    expect(screen.getByRole('link', { name: "Start an Analysis" })).toHaveAttribute('href', '/login?next=%2Fanalyses%2Fnew')
  })

  it('uses Filipino labels while identifying the videos as English', () => {
    renderWithProviders(<HomePage />, { lang: 'tl' })
    expect(screen.getByRole('button', { name: 'Queue types' })).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'How does Queueing works and what to record' })).toHaveAttribute('lang', 'en')
    expect(screen.getByText('Isang video · Parts 1 at 2')).toBeInTheDocument()
    expect(screen.getByText(/Narration at captions sa video sa English/)).toBeInTheDocument()
  })

  it('finds the data lesson in Help without showing a false no-results message', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HelpPage />)
    await user.type(screen.getByLabelText("Find Help"), 'theta variance')
    expect(screen.getByRole('heading', { name: 'How does Queueing works and what to record' })).toBeInTheDocument()
    expect(document.querySelectorAll('video')).toHaveLength(1)
    expect(screen.queryByText('No guide mentions all of these words.')).not.toBeInTheDocument()
  })
})
