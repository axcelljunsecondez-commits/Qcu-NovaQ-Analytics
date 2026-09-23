import { Suspense } from 'react'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { RegisterPage } from './RegisterPage'
import { VerifyEmailPage } from './VerifyEmailPage'
import { ForgotPasswordPage } from './ForgotPasswordPage'
import { ResetPasswordPage } from './ResetPasswordPage'

const registerMock = vi.fn()
const verifyMock = vi.fn()
const forgotMock = vi.fn()
const resetMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  googleLogin: vi.fn(),
  logout: vi.fn(),
  register: (...args: unknown[]) => registerMock(...args),
  resendVerification: vi.fn(async () => ({})),
  verifyEmail: (...args: unknown[]) => verifyMock(...args),
  forgotPassword: (...args: unknown[]) => forgotMock(...args),
  resetPassword: (...args: unknown[]) => resetMock(...args),
}))

beforeEach(() => {
  registerMock.mockReset().mockResolvedValue({})
  verifyMock.mockReset().mockResolvedValue({})
  forgotMock.mockReset().mockResolvedValue({})
  resetMock.mockReset().mockResolvedValue({})
  window.history.replaceState({}, '', '/')
})

describe('public authentication flows', () => {
  it('validates registration confirmation and shows generic sent state', async () => {
    const user = userEvent.setup()
    renderWithProviders(<RegisterPage />, { route: '/register' })
    await user.type(screen.getByLabelText('Email'), 'new@example.com')
    await user.type(screen.getByLabelText('Password'), 'password123')
    await user.type(screen.getByLabelText('Confirm password'), 'different123')
    await user.click(screen.getByRole('button', { name: 'Register' }))
    expect(await screen.findByText('Passwords do not match')).toBeInTheDocument()
    expect(registerMock).not.toHaveBeenCalled()
    await user.clear(screen.getByLabelText('Confirm password'))
    await user.type(screen.getByLabelText('Confirm password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Register' }))
    expect(await screen.findByText(/verification instructions have been sent/i)).toBeInTheDocument()
  })

  it('scrubs and verifies an email fragment token', async () => {
    window.history.replaceState({}, '', '/verify-email#token=secret-token-value')
    renderWithProviders(<VerifyEmailPage />, { route: '/verify-email' })
    await waitFor(() => expect(verifyMock).toHaveBeenCalledWith('secret-token-value'))
    expect(window.location.hash).toBe('')
    expect(await screen.findByText('Email verified. You can now sign in.')).toBeInTheDocument()
  })

  it('keeps forgot-password responses generic', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ForgotPasswordPage />, { route: '/forgot-password' })
    await user.type(screen.getByLabelText('Email'), 'unknown@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset email' }))
    expect(await screen.findByText(/password reset instructions have been sent/i)).toBeInTheDocument()
  })

  it('shows a recoverable error when the reset request cannot be sent', async () => {
    forgotMock.mockRejectedValueOnce(new Error('network unavailable'))
    const user = userEvent.setup()
    renderWithProviders(<ForgotPasswordPage />, { route: '/forgot-password' })
    await user.type(screen.getByLabelText('Email'), 'person@example.com')
    await user.click(screen.getByRole('button', { name: 'Send reset email' }))
    expect(await screen.findByRole('alert')).toHaveTextContent(/temporarily unavailable/i)
  })

  it('scrubs a reset token and validates password confirmation', async () => {
    window.history.replaceState({}, '', '/reset-password#token=reset-token-value')
    const user = userEvent.setup()
    renderWithProviders(<ResetPasswordPage />, { route: '/reset-password' })
    expect(window.location.hash).toBe('')
    await user.type(screen.getByLabelText('New password'), 'password123')
    await user.type(screen.getByLabelText('Confirm password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Reset password' }))
    await waitFor(() => expect(resetMock).toHaveBeenCalledWith('reset-token-value', 'password123'))
    expect(await screen.findByText('Password reset. You can now sign in.')).toBeInTheDocument()
  })

  it('keeps the reset token when the first render suspends', async () => {
    window.history.replaceState({}, '', '/reset-password#token=reset-token-value')
    let resolve!: () => void
    let ready = false
    const pending = new Promise<void>((r) => {
      resolve = () => {
        ready = true
        r()
      }
    })
    function SuspendOnce() {
      if (!ready) throw pending
      return null
    }
    renderWithProviders(
      <Suspense fallback={null}>
        <ResetPasswordPage />
        <SuspendOnce />
      </Suspense>,
      { route: '/reset-password' },
    )
    await act(async () => resolve())
    expect(await screen.findByLabelText('New password')).toBeInTheDocument()
    expect(window.location.hash).toBe('')
    const user = userEvent.setup()
    await user.type(screen.getByLabelText('New password'), 'password123')
    await user.type(screen.getByLabelText('Confirm password'), 'password123')
    await user.click(screen.getByRole('button', { name: 'Reset password' }))
    await waitFor(() => expect(resetMock).toHaveBeenCalledWith('reset-token-value', 'password123'))
  })
})
