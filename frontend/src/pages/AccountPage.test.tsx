import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { AccountPage } from './AccountPage'

const logoutMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: (...args: unknown[]) => logoutMock(...args),
}))

beforeEach(() => {
  logoutMock.mockReset()
  logoutMock.mockResolvedValue(undefined)
})

describe('AccountPage', () => {
  it('renders the email, role and created_at from the session user', async () => {
    renderWithProviders(<AccountPage />, { route: '/account' })
    expect(await screen.findByText('a@b.c')).toBeInTheDocument()
    expect(screen.getByText('admin')).toBeInTheDocument()
    const expected = new Intl.DateTimeFormat(undefined, { dateStyle: 'long' }).format(
      new Date('2026-01-01T00:00:00Z'),
    )
    expect(screen.getByText(expected)).toBeInTheDocument()
  })

  it('logs out and navigates to the login page', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/login" element={<div>login-page-marker</div>} />
        <Route path="/account" element={<AccountPage />} />
      </Routes>,
      { route: '/account' },
    )
    await screen.findByText('a@b.c')
    await user.click(screen.getByRole('button', { name: 'Logout' }))
    expect(logoutMock).toHaveBeenCalled()
    expect(await screen.findByText('login-page-marker')).toBeInTheDocument()
  })
})
