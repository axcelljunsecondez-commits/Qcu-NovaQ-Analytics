import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, act, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../../test/test-utils'
import { AppLayout, SIDEBAR_KEY } from './AppLayout'

vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(),
  logout: vi.fn(async () => ({})),
}))
vi.mock('../../api/analyses', () => ({
  listAnalyses: vi.fn(async () => ({ analyses: [] })),
}))

function renderLayout(route = '/analyses') {
  return renderWithProviders(
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="*" element={<p>Page body</p>} />
      </Route>
    </Routes>,
    { route },
  )
}

beforeEach(() => localStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('AppLayout hide-sidebar (D10)', () => {
  it('hides and shows the sidebar and remembers the choice on this device', async () => {
    const user = userEvent.setup()
    const { container, unmount } = renderLayout()
    await user.click(await screen.findByRole('button', { name: 'Hide sidebar' }))
    const show = screen.getByRole('button', { name: 'Show sidebar' })
    expect(show).toHaveAttribute('aria-expanded', 'false')
    expect(container.querySelector('.sidebar')).toHaveClass('is-collapsed')
    expect(localStorage.getItem(SIDEBAR_KEY)).toBe('hidden')
    unmount()

    const second = renderLayout()
    expect(await screen.findByRole('button', { name: 'Show sidebar' })).toBeInTheDocument()
    expect(second.container.querySelector('.sidebar')).toHaveClass('is-collapsed')
    await user.click(screen.getByRole('button', { name: 'Show sidebar' }))
    expect(localStorage.getItem(SIDEBAR_KEY)).toBe('shown')
    expect(second.container.querySelector('.sidebar')).not.toHaveClass('is-collapsed')
  })

  it('still hides and shows when storage is blocked', async () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    const user = userEvent.setup()
    renderLayout()
    await user.click(await screen.findByRole('button', { name: 'Hide sidebar' }))
    expect(screen.getByRole('button', { name: 'Show sidebar' })).toBeInTheDocument()
  })

  it('shows rail names on keyboard focus and hover, and Escape dismisses them', async () => {
    localStorage.setItem(SIDEBAR_KEY, 'hidden')
    const user = userEvent.setup()
    renderLayout()
    const link = await screen.findByRole('link', { name: 'Analysis Results' })
    expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument()
    act(() => link.focus())
    expect(await screen.findByTestId('tooltip')).toHaveTextContent('Analysis Results')
    await user.keyboard('{Escape}')
    expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument()
    await user.hover(screen.getByRole('link', { name: "Quick Calculator" }))
    expect(await screen.findByTestId('tooltip')).toHaveTextContent("Quick Calculator")
    await user.unhover(screen.getByRole('link', { name: "Quick Calculator" }))
    // Allow the short trigger-to-popup crossing grace, but retain the dismissal assertion.
    await waitFor(() => expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument())
  })

  it('does not repeat link names as tooltips while the sidebar is shown', async () => {
    renderLayout()
    const link = await screen.findByRole('link', { name: 'Analysis Results' })
    act(() => link.focus())
    expect(screen.queryByTestId('tooltip')).not.toBeInTheDocument()
  })
})

describe('AppHeader', () => {
  it('shows where the user is and the theme toggle', async () => {
    renderLayout('/settings/files')
    const crumbs = await screen.findByRole('navigation', { name: 'Breadcrumb' })
    expect(crumbs).toHaveTextContent('SettingsUploaded files')
    expect(screen.getByRole('button', { name: /Dark Mode|Light Mode/ })).toBeInTheDocument()
  })
})
