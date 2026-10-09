import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { renderWithProviders } from '../../test/test-utils'
import { initialsFor } from '../../lib/initials'
import { AccountMenu } from './AccountMenu'

const logoutMock = vi.fn(async () => ({}))
vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'maria.santos@example.com', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(),
  logout: () => logoutMock(),
}))

function Where() {
  return <p data-testid="where">{useLocation().pathname}</p>
}

function Harness() {
  return (
    <>
      <button type="button">Outside</button>
      <Routes>
        <Route path="*" element={<><AccountMenu /><Where /></>} />
      </Routes>
    </>
  )
}

async function openMenu() {
  const user = userEvent.setup()
  const button = await screen.findByRole('button', { name: 'Account menu for maria.santos@example.com' })
  await user.click(button)
  return { user, button, menu: screen.getByRole('menu') }
}

beforeEach(() => {
  logoutMock.mockClear()
  localStorage.clear()
})

describe('AccountMenu (spec §7.3, D10)', () => {
  it('shows initials and the email on a menu button that starts closed', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    const button = await screen.findByRole('button', { name: 'Account menu for maria.santos@example.com' })
    expect(button).toHaveAttribute('aria-haspopup', 'menu')
    expect(button).toHaveAttribute('aria-expanded', 'false')
    expect(button).toHaveTextContent('MS')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('lists email, Settings, Language, Get help and Log out, and focuses the first item', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    const { button, menu } = await openMenu()
    expect(button).toHaveAttribute('aria-expanded', 'true')
    expect(screen.getByText('maria.santos@example.com', { selector: '.account-menu-email' })).toBeInTheDocument()
    const items = Array.from(menu.querySelectorAll('[role="menuitem"], [role="menuitemradio"]')).map((item) => item.textContent?.trim())
    expect(items).toEqual(['Settings', '✓English', 'Filipino', 'Get help', 'Log out'])
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument()
    expect(screen.getByRole('menuitem', { name: 'Settings' })).toHaveFocus()
  })

  it('moves with arrow keys, Home and End, wrapping at both ends', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    const { user } = await openMenu()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('menuitemradio', { name: 'English' })).toHaveFocus()
    await user.keyboard('{End}')
    expect(screen.getByRole('menuitem', { name: 'Log out' })).toHaveFocus()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByRole('menuitem', { name: 'Settings' })).toHaveFocus()
    await user.keyboard('{ArrowUp}')
    expect(screen.getByRole('menuitem', { name: 'Log out' })).toHaveFocus()
    await user.keyboard('{Home}')
    expect(screen.getByRole('menuitem', { name: 'Settings' })).toHaveFocus()
  })

  it('closes on Escape and returns focus to the account button', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    const { user, button } = await openMenu()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    expect(button).toHaveFocus()
    expect(button).toHaveAttribute('aria-expanded', 'false')
  })

  it('closes on an outside click', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    const { user } = await openMenu()
    await user.click(screen.getByRole('button', { name: 'Outside' }))
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
  })

  it('opens Settings and Get help', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    let { user } = await openMenu()
    await user.click(screen.getByRole('menuitem', { name: 'Settings' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/settings')
    expect(screen.queryByRole('menu')).not.toBeInTheDocument()
    ;({ user } = await openMenu())
    await user.click(screen.getByRole('menuitem', { name: 'Get help' }))
    expect(screen.getByTestId('where')).toHaveTextContent('/help')
  })

  it('switches language and marks the chosen one', async () => {
    renderWithProviders(<Harness />, { route: '/analyses' })
    const { user } = await openMenu()
    await user.click(screen.getByRole('menuitemradio', { name: 'Filipino' }))
    expect(document.documentElement.lang).toBe('tl')
    expect(localStorage.getItem('novaq_lang')).toBe('tl')
    await user.click(screen.getByRole('button', { name: 'Menu ng account para sa maria.santos@example.com' }))
    expect(screen.getByRole('menuitemradio', { name: 'Filipino' })).toHaveAttribute('aria-checked', 'true')
    await user.click(screen.getByRole('menuitemradio', { name: 'English' }))
    expect(document.documentElement.lang).toBe('en')
  })

  it('logs out, clears cached data and goes to sign in', async () => {
    const { queryClient } = renderWithProviders(<Harness />, { route: '/analyses' })
    queryClient.setQueryData(['analyses'], { analyses: [] })
    const { user } = await openMenu()
    await user.click(screen.getByRole('menuitem', { name: 'Log out' }))
    await waitFor(() => expect(screen.getByTestId('where')).toHaveTextContent('/login'))
    expect(logoutMock).toHaveBeenCalledTimes(1)
    expect(queryClient.getQueryData(['analyses'])).toBeUndefined()
    expect(queryClient.getQueryData(['me'])).toBeNull()
  })
})

describe('initialsFor', () => {
  it.each([
    ['maria.santos@example.com', 'MS'],
    ['you@example.com', 'YO'],
    ['j@example.com', 'J'],
    ['ana_reyes-cruz@example.com', 'AR'],
  ])('%s → %s', (email, initials) => {
    expect(initialsFor(email)).toBe(initials)
  })
})
