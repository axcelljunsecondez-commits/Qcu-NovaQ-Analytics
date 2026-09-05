import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, render } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { RouterProvider } from 'react-router-dom'
import { renderWithProviders, makeQueryClient } from '../test/test-utils'
import { LoginPage } from './LoginPage'
import { createAppRouter } from '../router'

const meMock = vi.fn()
const loginMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: (...args: unknown[]) => loginMock(...args),
  logout: vi.fn(async () => ({})),
}))

const adminUser = {
  id: 1,
  email: 'a@b.c',
  role: 'admin' as const,
  active: true,
  created_at: '2026-01-01T00:00:00Z',
}

beforeEach(() => {
  meMock.mockReset()
  loginMock.mockReset()
  meMock.mockResolvedValue({ user: null })
})

describe('LoginPage', () => {
  it('renders email, password fields and a submit button', () => {
    renderWithProviders(<LoginPage />, { route: '/login' })
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByLabelText('Password')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument()
  })

  it('submits credentials and shows the logged-in user email', async () => {
    loginMock.mockResolvedValue({ user: adminUser })
    window.history.pushState({}, '', '/login')
    const qc = makeQueryClient()
    render(
      <QueryClientProvider client={qc}>
        <RouterProvider router={createAppRouter()} />
      </QueryClientProvider>,
    )
    const user = userEvent.setup()
    await user.type(await screen.findByLabelText('Email'), 'a@b.c')
    await user.type(screen.getByLabelText('Password'), 'secret')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    await waitFor(() => {
      expect(loginMock).toHaveBeenCalledWith({ email: 'a@b.c', password: 'secret' })
    })
    await waitFor(() => {
      expect(screen.getByText('a@b.c')).toBeInTheDocument()
    })
  })

  it('shows a translated error message on failed login', async () => {
    loginMock.mockRejectedValue({ response: { status: 401 } })
    const user = userEvent.setup()
    renderWithProviders(<LoginPage />, { route: '/login' })
    await user.type(screen.getByLabelText('Email'), 'a@b.c')
    await user.type(screen.getByLabelText('Password'), 'wrong')
    await user.click(screen.getByRole('button', { name: 'Sign in' }))
    expect(await screen.findByText('Invalid email or password.')).toBeInTheDocument()
  })

  it('renders Tagalog labels when language is tl', () => {
    renderWithProviders(<LoginPage />, { route: '/login', lang: 'tl' })
    expect(screen.getByLabelText('Email')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Mag-sign in' })).toBeInTheDocument()
  })
})
