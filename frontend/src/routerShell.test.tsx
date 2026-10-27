import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor } from '@testing-library/react'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { createAppRouter } from './router'
import { makeQueryClient, testI18n } from './test/test-utils'

const meMock = vi.fn()

vi.mock('./api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(),
  logout: vi.fn(async () => ({})),
  authConfig: vi.fn(async () => ({ google_enabled: false, google_client_id: null })),
  googleNonce: vi.fn(),
  googleLogin: vi.fn(),
  linkGoogle: vi.fn(),
  changePassword: vi.fn(),
  forgotPassword: vi.fn(),
}))
vi.mock('./api/analyses', () => ({
  listAnalyses: vi.fn(async () => ({ analyses: [] })),
  archiveAnalysis: vi.fn(),
}))
vi.mock('./api/datasets', () => ({
  listDatasets: vi.fn(async () => ({ datasets: [] })),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))
vi.mock('./api/users', () => ({
  listUsers: vi.fn(async () => ({ users: [] })),
  createUser: vi.fn(),
  updateUser: vi.fn(),
}))

function user(role: 'admin' | 'analyst') {
  return { user: { id: 1, email: 'ana@example.com', role, active: true, created_at: '2026-01-01T00:00:00Z', has_password: true } }
}

function renderAt(path: string) {
  const router = createMemoryRouter(createAppRouter().routes, { initialEntries: [path] })
  render(
    <QueryClientProvider client={makeQueryClient()}>
      <I18nextProvider i18n={testI18n()}>
        <RouterProvider router={router} />
      </I18nextProvider>
    </QueryClientProvider>,
  )
  return router
}

beforeEach(() => {
  meMock.mockReset()
  meMock.mockResolvedValue(user('analyst'))
  void testI18n().changeLanguage('en')
})

describe('compatibility redirects (spec §5)', () => {
  it.each([
    ['/dashboard', '/analyses'],
    ['/datasets', '/settings/files'],
    ['/analysis', '/tools/calculator'],
    ['/account', '/settings/account'],
    ['/settings', '/settings/account'],
    ['/settings/unknown-section', '/settings/account'],
  ])('%s lands on %s', async (from, to) => {
    const router = renderAt(from)
    await waitFor(() => expect(router.state.location.pathname).toBe(to))
  })

  it('/admin lands on Settings → Users and still forbids analysts', async () => {
    const router = renderAt('/admin')
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/users'))
    expect(await screen.findByText('You do not have permission to view this page.')).toBeInTheDocument()
  })

  it('/admin lands on Settings → Users for an admin', async () => {
    meMock.mockResolvedValue(user('admin'))
    const router = renderAt('/admin')
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/users'))
    expect(await screen.findByRole('link', { name: 'Users' })).toHaveAttribute('aria-current', 'page')
  })

  it('Settings hides the Users section from analysts', async () => {
    renderAt('/settings/account')
    expect(await screen.findByRole('navigation', { name: 'Settings sections' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Uploaded files' })).toHaveAttribute('href', '/settings/files')
    expect(screen.queryByRole('link', { name: 'Users' })).not.toBeInTheDocument()
  })
})

describe('unknown paths', () => {
  it('send a signed-in user to My analyses', async () => {
    const router = renderAt('/no-such-page')
    await waitFor(() => expect(router.state.location.pathname).toBe('/analyses'))
  })

  it('send a signed-out visitor to the public Home page', async () => {
    meMock.mockResolvedValue({ user: null })
    const router = renderAt('/no-such-page')
    await waitFor(() => expect(router.state.location.pathname).toBe('/'))
    expect(await screen.findByRole('heading', { level: 1, name: /Smarter Staffing,.*Shorter Queues\./ })).toBeInTheDocument()
  })
})
