import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClientProvider } from '@tanstack/react-query'
import { I18nextProvider } from 'react-i18next'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { createAppRouter } from './router'
import { INTENT_KEY } from './auth/intent'
import { makeQueryClient, testI18n } from './test/test-utils'

const meMock = vi.fn()
const loginMock = vi.fn()
const googleLoginMock = vi.fn()

const analyst = { id: 3, email: 'new@example.com', role: 'analyst', active: true, created_at: '2026-10-09T00:00:00Z', has_password: true }

vi.mock('./api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: (...args: unknown[]) => loginMock(...args),
  logout: vi.fn(async () => ({})),
  authConfig: vi.fn(async () => ({ google_sign_in_enabled: false, google_client_id: null })),
  googleNonce: vi.fn(),
  googleLogin: (...args: unknown[]) => googleLoginMock(...args),
  register: vi.fn(async () => ({ detail: 'sent' })),
  resendVerification: vi.fn(),
  linkGoogle: vi.fn(),
  changePassword: vi.fn(),
  forgotPassword: vi.fn(),
}))
// Google's script cannot run in tests; this stand-in exercises the same
// loginWithGoogle → onSuccess path the real button uses after a credential.
vi.mock('./auth/GoogleSignInButton', async () => {
  const { useAuth } = await import('./auth/useAuth')
  return {
    GoogleSignInButton: ({ onSuccess }: { onSuccess?: () => void }) => {
      const { loginWithGoogle } = useAuth()
      return <button type="button" onClick={async () => { await loginWithGoogle('credential'); onSuccess?.() }}>Test Google sign-in</button>
    },
  }
})
vi.mock('./api/analyses', () => ({
  listAnalyses: vi.fn(async () => ({ analyses: [] })),
  archiveAnalysis: vi.fn(),
  createAnalysis: vi.fn(),
}))
vi.mock('./api/preferences', () => ({
  getPreferences: vi.fn(async () => ({ operation_type: null, preferred_terminology: {} })),
  savePreferences: vi.fn(),
}))

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

function where(router: ReturnType<typeof renderAt>) {
  const { pathname, search, hash } = router.state.location
  return `${pathname}${search}${hash}`
}

async function signInWithPassword() {
  const user = userEvent.setup()
  await user.type(await screen.findByLabelText('Email'), analyst.email)
  await user.type(screen.getByLabelText('Password'), 'long-password')
  await user.click(screen.getByRole('button', { name: 'Sign in' }))
}

beforeEach(() => {
  sessionStorage.clear()
  meMock.mockReset()
  loginMock.mockReset()
  googleLoginMock.mockReset()
  meMock.mockResolvedValue({ user: null })
  loginMock.mockImplementation(async () => {
    meMock.mockResolvedValue({ user: analyst })
    return { user: analyst }
  })
  googleLoginMock.mockImplementation(async () => {
    meMock.mockResolvedValue({ user: analyst })
    return { user: analyst }
  })
  void testI18n().changeLanguage('en')
})

describe('public Home (spec §7.1)', () => {
  it('has exactly one Start an analysis, a Sign in link and both line pictures', async () => {
    renderAt('/')
    expect(await screen.findByRole('heading', { level: 1, name: /See how long your customers wait/ })).toBeInTheDocument()
    const starts = screen.getAllByRole('link', { name: 'Start an analysis' })
    expect(starts).toHaveLength(1)
    expect(starts[0]).toHaveAttribute('href', '/login?next=%2Fanalyses%2Fnew')
    expect(within(screen.getByRole('banner')).queryByRole('link', { name: 'Start an analysis' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login')
    expect(screen.getByRole('img', { name: /one shared line/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /three separate lines/ })).toBeInTheDocument()
    expect(screen.getByLabelText('Language')).toBeInTheDocument()
  })

  it('offers My analyses and a direct Start to a signed-in visitor', async () => {
    meMock.mockResolvedValue({ user: analyst })
    renderAt('/')
    expect(await screen.findByRole('link', { name: 'Go to My analyses' })).toHaveAttribute('href', '/analyses')
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Start an analysis' })).toHaveAttribute('href', '/analyses/new')
  })

  it('switches the page language from the dropdown', async () => {
    renderAt('/')
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText('Language'), 'tl')
    expect(await screen.findByRole('link', { name: 'Magsimula ng pagsusuri' })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Wika'), 'en')
  })
})

describe('sign-in intent (spec §7.2)', () => {
  it('Start → sign in with a password → New analysis', async () => {
    const router = renderAt('/')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('link', { name: 'Start an analysis' }))
    await waitFor(() => expect(where(router)).toBe('/login?next=%2Fanalyses%2Fnew'))
    await signInWithPassword()
    await waitFor(() => expect(where(router)).toBe('/analyses/new'))
  })

  it('Start → sign in with Google → New analysis', async () => {
    const router = renderAt('/login?next=%2Fanalyses%2Fnew')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Test Google sign-in' }))
    await waitFor(() => expect(where(router)).toBe('/analyses/new'))
    expect(googleLoginMock).toHaveBeenCalledWith('credential')
  })

  it('a normal sign-in lands on My analyses', async () => {
    const router = renderAt('/login')
    await signInWithPassword()
    await waitFor(() => expect(where(router)).toBe('/analyses'))
  })

  it('ignores an unsafe next and lands on My analyses', async () => {
    const router = renderAt('/login?next=%2F%2Fevil.example')
    await signInWithPassword()
    await waitFor(() => expect(where(router)).toBe('/analyses'))
  })

  it('returns to a deep link with its query and hash', async () => {
    const router = renderAt('/tools/calculator?model=mmc#result')
    await waitFor(() => expect(router.state.location.pathname).toBe('/login'))
    await signInWithPassword()
    await waitFor(() => expect(where(router)).toBe('/tools/calculator?model=mmc#result'))
  })

  it('keeps the intent through registration and email verification for this tab', async () => {
    const router = renderAt('/login?next=%2Fanalyses%2Fnew')
    const user = userEvent.setup()
    const register = await screen.findByRole('link', { name: 'Register' })
    expect(register).toHaveAttribute('href', '/register?next=%2Fanalyses%2Fnew')
    await user.click(register)
    await waitFor(() => expect(sessionStorage.getItem(INTENT_KEY)).toBe('/analyses/new'))
    await router.navigate('/login')
    await screen.findByRole('heading', { name: 'Sign in to NovaQ' })
    await signInWithPassword()
    await waitFor(() => expect(where(router)).toBe('/analyses/new'))
    expect(sessionStorage.getItem(INTENT_KEY)).toBeNull()
  })
})

describe('no mandatory onboarding (spec §12, D2)', () => {
  it('a user who never completed onboarding reaches My analyses', async () => {
    meMock.mockResolvedValue({ user: analyst })
    const router = renderAt('/analyses')
    expect(await screen.findByRole('heading', { level: 1, name: 'My Analyses' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/analyses')
  })

  it('/onboarding opens Settings → Preferences', async () => {
    meMock.mockResolvedValue({ user: analyst })
    const router = renderAt('/onboarding?replay=1')
    await waitFor(() => expect(router.state.location.pathname).toBe('/settings/preferences'))
    expect(await screen.findByRole('heading', { level: 1, name: 'Preferences' })).toBeInTheDocument()
  })
})
