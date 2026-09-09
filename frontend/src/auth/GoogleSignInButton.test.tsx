import { act, screen, waitFor } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { renderWithProviders } from '../test/test-utils'
import { GoogleSignInButton } from './GoogleSignInButton'

const mocks = vi.hoisted(() => ({
  authConfig: vi.fn(),
  googleNonce: vi.fn(),
  googleLogin: vi.fn(),
  initialize: vi.fn(),
  renderButton: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
  authConfig: (...args: unknown[]) => mocks.authConfig(...args),
  googleNonce: (...args: unknown[]) => mocks.googleNonce(...args),
  googleLogin: (...args: unknown[]) => mocks.googleLogin(...args),
}))

beforeEach(() => {
  mocks.authConfig.mockReset()
  mocks.googleNonce.mockReset().mockResolvedValue({ nonce: 'server-nonce' })
  mocks.googleLogin.mockReset().mockResolvedValue({
    user: { id: 1, email: 'a@gmail.com', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' },
  })
  mocks.initialize.mockReset()
  mocks.renderButton.mockReset()
  window.google = {
    accounts: {
      id: {
        initialize: mocks.initialize,
        renderButton: mocks.renderButton,
        disableAutoSelect: vi.fn(),
      },
    },
  }
})

afterEach(() => {
  delete window.google
})

describe('GoogleSignInButton', () => {
  it('stays hidden when Google is disabled', async () => {
    mocks.authConfig.mockResolvedValue({ google_sign_in_enabled: false, google_client_id: null })
    renderWithProviders(<GoogleSignInButton />)
    await waitFor(() => expect(mocks.authConfig).toHaveBeenCalled())
    expect(screen.queryByLabelText('Continue with Google')).not.toBeInTheDocument()
  })

  it('initializes GIS with a server nonce and enters the normal auth session', async () => {
    mocks.authConfig.mockResolvedValue({
      google_sign_in_enabled: true,
      google_client_id: 'client.apps.googleusercontent.com',
    })
    renderWithProviders(<GoogleSignInButton />)
    await waitFor(() => expect(mocks.initialize).toHaveBeenCalled())
    const options = mocks.initialize.mock.calls[0][0] as {
      nonce: string
      callback: (response: { credential: string }) => Promise<void>
    }
    expect(options.nonce).toBe('server-nonce')
    expect(mocks.renderButton).toHaveBeenCalled()
    await act(() => options.callback({ credential: 'complete-google-id-token' }))
    expect(mocks.googleLogin).toHaveBeenCalledWith('complete-google-id-token')
  })
})
