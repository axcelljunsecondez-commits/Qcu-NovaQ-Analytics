import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { AppLayout } from '../components/layout/AppLayout'
import { SettingsPage } from './SettingsPage'

const meMock = vi.fn()
vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(),
  logout: vi.fn(async () => ({})),
  authConfig: vi.fn(async () => ({ google_enabled: false, google_client_id: null })),
  googleNonce: vi.fn(),
  linkGoogle: vi.fn(),
  changePassword: vi.fn(),
  forgotPassword: vi.fn(async () => ({ detail: 'ok' })),
}))
vi.mock('../api/analyses', () => ({
  listAnalyses: vi.fn(async () => ({ analyses: [] })),
}))
vi.mock('../api/datasets', () => ({
  listDatasets: vi.fn(async () => ({ datasets: [] })),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

function account(hasPassword: boolean) {
  return {
    user: {
      id: 1,
      email: 'g@example.com',
      role: 'analyst',
      active: true,
      created_at: '2026-01-01T00:00:00Z',
      email_verified: true,
      has_password: hasPassword,
      auth_methods: hasPassword ? ['password'] : ['google'],
    },
  }
}

function renderSettings(route: string) {
  return renderWithProviders(
    <Routes>
      <Route element={<AppLayout />}>
        <Route path="/settings/:section" element={<SettingsPage />} />
      </Route>
    </Routes>,
    { route },
  )
}

beforeEach(() => {
  meMock.mockReset()
  localStorage.clear()
  document.documentElement.dataset.theme = 'light'
})

describe('Settings (spec §7.10)', () => {
  it('offers the set-password email to an account without a password', async () => {
    meMock.mockResolvedValue(account(false))
    renderSettings('/settings/account')
    expect(await screen.findByRole('button', { name: 'Send reset email' })).toBeInTheDocument()
    expect(screen.queryByLabelText('Current password')).not.toBeInTheDocument()
  })

  it('offers the password change form to an account with a password', async () => {
    meMock.mockResolvedValue(account(true))
    renderSettings('/settings/account')
    expect(await screen.findByLabelText('Current password')).toBeInTheDocument()
  })

  it('shows the existing uploaded-files management under Uploaded files', async () => {
    meMock.mockResolvedValue(account(true))
    renderSettings('/settings/files')
    expect(await screen.findByRole('heading', { level: 1, name: 'Datasets' })).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Uploaded files' })).toHaveAttribute('aria-current', 'page')
  })

  it('keeps the header and Appearance theme controls in agreement', async () => {
    meMock.mockResolvedValue(account(true))
    const user = userEvent.setup()
    renderSettings('/settings/appearance')
    await screen.findByRole('heading', { level: 1, name: 'Appearance' })
    const toggles = screen.getAllByRole('button', { name: 'Dark Mode' })
    expect(toggles).toHaveLength(2)
    await user.click(toggles[1])
    expect(screen.getAllByRole('button', { name: 'Light Mode' })).toHaveLength(2)
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('novaq_theme')).toBe('dark')
    expect(screen.getByRole('group', { name: 'Language' })).toBeInTheDocument()
  })
})
