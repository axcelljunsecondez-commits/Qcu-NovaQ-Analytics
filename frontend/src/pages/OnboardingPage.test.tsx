import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { OnboardingPage } from './OnboardingPage'

const getStatusMock = vi.fn()
const completeMock = vi.fn()

vi.mock('../api/onboarding', () => ({
  getOnboardingStatus: (...args: unknown[]) => getStatusMock(...args),
  completeOnboarding: (...args: unknown[]) => completeMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' } })),
  login: vi.fn(),
  logout: vi.fn(),
}))

beforeEach(() => {
  getStatusMock.mockReset().mockResolvedValue({ completed: false, operation_type: null, preferred_terminology: {} })
  completeMock.mockReset().mockResolvedValue({ completed: true, operation_type: 'retail', preferred_terminology: { service_point: 'cashiers', customer: 'customers' } })
})

describe('OnboardingPage', () => {
  it('requires real preferences and persists them without a skip path', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/onboarding" element={<OnboardingPage />} />
        <Route path="/analyses" element={<div>Analyses</div>} />
      </Routes>,
      { route: '/onboarding' },
    )
    expect(await screen.findByRole('heading', { name: 'Welcome to NovaQ' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /skip/i })).not.toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Save and enter NovaQ' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Operation type'), 'retail')
    await user.selectOptions(screen.getByLabelText('What do you call service points?'), 'cashiers')
    await user.selectOptions(screen.getByLabelText('What do you call people receiving service?'), 'customers')
    await user.click(submit)
    await waitFor(() => expect(completeMock).toHaveBeenCalled())
    expect(completeMock.mock.calls[0][0]).toEqual({
      operation_type: 'retail',
      preferred_terminology: { service_point: 'cashiers', customer: 'customers' },
    })
    expect(await screen.findByText('Analyses')).toBeInTheDocument()
  })

  it('renders completed onboarding when explicitly replayed', async () => {
    getStatusMock.mockResolvedValue({ completed: true, operation_type: 'retail', preferred_terminology: { service_point: 'cashiers', customer: 'customers' } })
    renderWithProviders(<OnboardingPage />, { route: '/onboarding?replay=1' })
    expect(await screen.findByText('Onboarding replay')).toBeInTheDocument()
    expect(screen.getByLabelText('Operation type')).toHaveValue('retail')
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
  })
})
