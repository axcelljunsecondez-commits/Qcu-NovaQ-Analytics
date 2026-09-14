import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes, useLocation } from 'react-router-dom'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test/test-utils'
import { RequireOnboarding } from './RequireOnboarding'

const getOnboardingStatusMock = vi.fn()

vi.mock('../api/onboarding', () => ({
  getOnboardingStatus: (...args: unknown[]) => getOnboardingStatusMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' } })),
  login: vi.fn(),
  logout: vi.fn(),
}))

function LocationProbe() {
  const location = useLocation()
  return <div>{location.pathname}:{String((location.state as { from?: string } | null)?.from)}</div>
}

function GuardRoutes() {
  return (
    <Routes>
      <Route path="/onboarding" element={<LocationProbe />} />
      <Route element={<RequireOnboarding />}>
        <Route path="/dashboard" element={<div>Protected dashboard</div>} />
      </Route>
    </Routes>
  )
}

beforeEach(() => getOnboardingStatusMock.mockReset())

describe('RequireOnboarding', () => {
  it('redirects an incomplete first-time user and preserves the intended route', async () => {
    getOnboardingStatusMock.mockResolvedValue({ completed: false, operation_type: null, preferred_terminology: {} })
    renderWithProviders(<GuardRoutes />, { route: '/dashboard' })
    expect(await screen.findByText('/onboarding:/dashboard')).toBeInTheDocument()
  })

  it('allows a returning user through without replaying onboarding', async () => {
    getOnboardingStatusMock.mockResolvedValue({ completed: true, operation_type: 'retail', preferred_terminology: {} })
    renderWithProviders(<GuardRoutes />, { route: '/dashboard' })
    expect(await screen.findByText('Protected dashboard')).toBeInTheDocument()
  })

  it('shows an error instead of silently bypassing the gate', async () => {
    getOnboardingStatusMock.mockResolvedValue(undefined)
    renderWithProviders(<GuardRoutes />, { route: '/dashboard' })
    expect(await screen.findByText('The server encountered an error. Please try again.')).toBeInTheDocument()
    expect(screen.queryByText('Protected dashboard')).not.toBeInTheDocument()
  })
})
