import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { AccountPage } from './AccountPage'

const logoutMock = vi.fn()
const changePasswordMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: (...args: unknown[]) => logoutMock(...args),
  changePassword: (...args: unknown[]) => changePasswordMock(...args),
}))

beforeEach(() => {
  logoutMock.mockReset()
  logoutMock.mockResolvedValue(undefined)
  changePasswordMock.mockReset()
  changePasswordMock.mockResolvedValue({})
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

  it('renders the password change form', async () => {
    renderWithProviders(<AccountPage />, { route: '/account' })
    await screen.findByText('a@b.c')
    expect(screen.getByLabelText('Current password')).toBeInTheDocument()
    expect(screen.getByLabelText('New password')).toBeInTheDocument()
    expect(screen.getByLabelText('Confirm new password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Change password' })).toBeInTheDocument()
  })

  it('blocks submit when the confirmation does not match', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AccountPage />, { route: '/account' })
    await screen.findByText('a@b.c')
    await user.type(screen.getByLabelText('Current password'), 'old')
    await user.type(screen.getByLabelText('New password'), 'new1')
    await user.type(screen.getByLabelText('Confirm new password'), 'new2')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(changePasswordMock).not.toHaveBeenCalled()
  })

  it('calls the API, shows success, and does not log out the current session', async () => {
    const user = userEvent.setup()
    renderWithProviders(<AccountPage />, { route: '/account' })
    await screen.findByText('a@b.c')
    await user.type(screen.getByLabelText('Current password'), 'old')
    await user.type(screen.getByLabelText('New password'), 'new1')
    await user.type(screen.getByLabelText('Confirm new password'), 'new1')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Password changed')).toBeInTheDocument()
    expect(changePasswordMock).toHaveBeenCalledWith('old', 'new1')
    expect(logoutMock).not.toHaveBeenCalled()
    expect(screen.getByText('a@b.c')).toBeInTheDocument()
  })

  it('shows a distinct message for a wrong current password', async () => {
    const user = userEvent.setup()
    changePasswordMock.mockRejectedValue({ response: { status: 401 } })
    renderWithProviders(<AccountPage />, { route: '/account' })
    await screen.findByText('a@b.c')
    await user.type(screen.getByLabelText('Current password'), 'wrong')
    await user.type(screen.getByLabelText('New password'), 'new1')
    await user.type(screen.getByLabelText('Confirm new password'), 'new1')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Current password is incorrect')).toBeInTheDocument()
    expect(logoutMock).not.toHaveBeenCalled()
  })

  it('shows a generic message for other failures', async () => {
    const user = userEvent.setup()
    changePasswordMock.mockRejectedValue({ response: { status: 500 } })
    renderWithProviders(<AccountPage />, { route: '/account' })
    await screen.findByText('a@b.c')
    await user.type(screen.getByLabelText('Current password'), 'old')
    await user.type(screen.getByLabelText('New password'), 'new1')
    await user.type(screen.getByLabelText('Confirm new password'), 'new1')
    await user.click(screen.getByRole('button', { name: 'Change password' }))
    expect(await screen.findByText('Could not change password')).toBeInTheDocument()
  })
})
