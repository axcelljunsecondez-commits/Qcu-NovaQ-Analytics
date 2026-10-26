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
    const headerButton = within(header).getByRole('button', { name: 'How it works' })
    expect(headerButton).not.toHaveAttribute('href')
    expect(headerButton).toHaveAttribute('aria-expanded', 'false')
    expect(screen.queryByRole('heading', { name: 'Add your records' })).not.toBeInTheDocument()
    await user.click(headerButton)
    expect(headerButton).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByRole('heading', { name: 'Add your records' })).toBeInTheDocument()
    const next = screen.getByRole('button', { name: 'Next: How it works' })
    await user.click(next);expect(screen.getByRole('heading', { name: 'See suggested plans' })).toBeInTheDocument()
    await user.click(next);expect(screen.getByRole('heading', { name: 'Watch your day' })).toBeInTheDocument()
    await user.click(next);expect(screen.getByRole('heading', { name: 'Add your records' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Previous: How it works' }))
    expect(screen.getByRole('heading', { name: 'Watch your day' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'How it works', description: 'From your records to a service plan' }))
    expect(document.getElementById('home-how-it-works-panel')).toHaveAttribute('inert')
    expect(window.scrollTo).not.toHaveBeenCalled()
    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()
  })

  it('starts with both guides closed and cycles separate → shared → separate without touching the analysis link', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HomePage />)
    const trigger = screen.getByRole('button', { name: 'Queue types' })
    expect(trigger).toHaveAttribute('aria-expanded', 'false')
    await user.click(trigger)
    expect(screen.getByRole('img', { name: /three separate lines/ })).toBeInTheDocument()
    const next = screen.getByRole('button', { name: 'Next: Queue types' })
    await user.click(next);expect(screen.getByRole('img', { name: /one shared line/ })).toBeInTheDocument()
    await user.click(next);expect(screen.getByRole('img', { name: /three separate lines/ })).toBeInTheDocument()
    expect(screen.getAllByRole('link', { name: 'Start an analysis' })).toHaveLength(1)
    expect(screen.getByRole('link', { name: 'Start an analysis' })).toHaveAttribute('href', '/login?next=%2Fanalyses%2Fnew')
  })

  it('uses Filipino labels while identifying the videos as English', () => {
    renderWithProviders(<HomePage />, { lang: 'tl' })
    expect(screen.getByRole('button', { name: /^Mga uri ng pila/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Ano ang dapat itala ng inyong team/ })).toBeInTheDocument()
    expect(screen.getByText(/Narration at nakikitang captions sa English/)).toBeInTheDocument()
  })

  it('finds the data lesson in Help without showing a false no-results message', async () => {
    const user = userEvent.setup()
    renderWithProviders(<HelpPage />)
    await user.type(screen.getByLabelText('Find help'), 'theta variance')
    expect(within(screen.getByRole('group', { name: 'Choose a Queueing Theory 101 lesson' })).getByRole('button', { name: /What your team should record/ })).toBeInTheDocument()
    expect(screen.queryByText('No guide mentions all of these words.')).not.toBeInTheDocument()
  })
})
