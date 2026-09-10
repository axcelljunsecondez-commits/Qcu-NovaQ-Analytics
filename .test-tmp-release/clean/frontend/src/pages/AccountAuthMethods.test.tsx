import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/test-utils'
import { AccountPage } from './AccountPage'

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: {
      id: 7,
      email: 'google@gmail.com',
      role: 'analyst',
      active: true,
      created_at: '2026-01-01T00:00:00Z',
      email_verified: true,
      has_password: false,
      auth_methods: ['google'],
    },
  })),
  login: vi.fn(),
  googleLogin: vi.fn(),
  logout: vi.fn(),
  forgotPassword: vi.fn(async () => ({})),
  linkGoogle: vi.fn(),
  changePassword: vi.fn(),
  authConfig: vi.fn(async () => ({ google_sign_in_enabled: false, google_client_id: null })),
  googleNonce: vi.fn(),
}))

describe('AccountPage authentication methods', () => {
  it('shows reset-based Set Password for a Google-only user', async () => {
    renderWithProviders(<AccountPage />, { route: '/account' })
    expect(await screen.findByText('google@gmail.com')).toBeInTheDocument()
    expect(screen.getByText('Verified')).toBeInTheDocument()
    expect(screen.getByText('google')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Set password' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()
  })
})
