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

function renderFirstTime() {
  renderWithProviders(
    <Routes>
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/analyses" element={<div>Analyses</div>} />
    </Routes>,
    { route: '/onboarding' },
  )
}

describe('OnboardingPage', () => {
  it('walks through every slide and requires real preferences before saving', async () => {
    const user = userEvent.setup()
    renderFirstTime()
    expect(await screen.findByRole('heading', { name: 'Welcome to NovaQ' })).toBeInTheDocument()
    expect(screen.getByText('Step 1 of 5')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Back' })).not.toBeInTheDocument()
    // Slides the user has not reached cannot be jumped to.
    expect(screen.getByRole('button', { name: /Terminology/ })).toBeDisabled()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('heading', { name: 'The NovaQ workflow' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Optimize/ }))
    expect(screen.getByRole('button', { name: /Optimize/ })).toHaveAttribute('aria-pressed', 'true')
    expect(screen.getByText(/separate queues get their schedule checked lane by lane/)).toBeInTheDocument()

    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('heading', { name: 'Choose your queue type' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('heading', { name: 'Using NovaQ with a shared queue' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Next' }))

    expect(screen.getByText('Step 5 of 5')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument()
    const submit = screen.getByRole('button', { name: 'Save and enter NovaQ' })
    expect(submit).toBeDisabled()
    await user.selectOptions(screen.getByLabelText('Operation type'), 'retail')
    await user.selectOptions(screen.getByLabelText('What do you call service points?'), 'cashiers')
    await user.selectOptions(screen.getByLabelText('What do you call people receiving service?'), 'customers')
    expect(screen.getByText('Your terms: Cashiers · Customers')).toBeInTheDocument()
    await user.click(submit)
    await waitFor(() => expect(completeMock).toHaveBeenCalled())
    expect(completeMock.mock.calls[0][0]).toEqual({
      operation_type: 'retail',
      preferred_terminology: { service_point: 'cashiers', customer: 'customers' },
    })
    expect(await screen.findByText('Analyses')).toBeInTheDocument()
  })

  it('skips the intro to the preferences slide, which still has to be saved', async () => {
    const user = userEvent.setup()
    renderFirstTime()
    await user.click(await screen.findByRole('button', { name: 'Skip intro' }))
    expect(screen.getByRole('heading', { name: 'Set your workspace terminology' })).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Skip intro' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save and enter NovaQ' })).toBeDisabled()
    expect(screen.getByText(/NovaQ pages keep their standard terms/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Back' }))
    expect(screen.getByRole('heading', { name: 'Using NovaQ with a shared queue' })).toBeInTheDocument()
  })

  it('shows the guide for the queue type picked, and can switch between guides', async () => {
    const user = userEvent.setup()
    renderFirstTime()
    await user.click(await screen.findByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    await user.click(screen.getByRole('radio', { name: /Separate queues/ }))
    await user.click(screen.getByRole('button', { name: 'Next' }))
    expect(screen.getByRole('heading', { name: 'Using NovaQ with separate queues' })).toBeInTheDocument()
    expect(screen.getByText(/Every upload row needs a queue_id/)).toBeInTheDocument()
    expect(screen.getByText(/Every scheduled lane stays open/)).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'See the shared-queue guide' }))
    expect(screen.getByRole('heading', { name: 'Using NovaQ with a shared queue' })).toBeInTheDocument()
    expect(screen.getByText(/No queue_id column is needed/)).toBeInTheDocument()
  })

  it('requires typed labels for "Other" choices and saves them trimmed', async () => {
    const user = userEvent.setup()
    renderFirstTime()
    await user.click(await screen.findByRole('button', { name: 'Skip intro' }))
    const submit = screen.getByRole('button', { name: 'Save and enter NovaQ' })
    expect(screen.queryByLabelText('Name your operation')).not.toBeInTheDocument()

    await user.selectOptions(screen.getByLabelText('Operation type'), 'other')
    await user.selectOptions(screen.getByLabelText('What do you call service points?'), 'other')
    await user.selectOptions(screen.getByLabelText('What do you call people receiving service?'), 'patients')
    const operationName = screen.getByLabelText('Name your operation')
    expect(operationName).toHaveAttribute('maxLength', '50')
    await user.type(operationName, '   ')
    expect(submit).toBeDisabled()
    await user.type(operationName, 'Laundry shop ')
    const [plural] = screen.getAllByLabelText('Name for more than one')
    const [singular] = screen.getAllByLabelText('Name for one')
    await user.type(plural, ' Nurses ')
    expect(submit).toBeDisabled()
    await user.type(singular, 'Nurse')
    expect(submit).toBeEnabled()
    expect(screen.getByText('Your terms: Nurses · Patients')).toBeInTheDocument()

    await user.click(submit)
    await waitFor(() => expect(completeMock).toHaveBeenCalled())
    expect(completeMock.mock.calls[0][0]).toEqual({
      operation_type: 'other',
      preferred_terminology: {
        service_point: 'other',
        customer: 'patients',
        operation_label: 'Laundry shop',
        service_point_label: 'Nurses',
        service_point_label_singular: 'Nurse',
      },
    })
  })

  it('renders completed onboarding when explicitly replayed', async () => {
    getStatusMock.mockResolvedValue({ completed: true, operation_type: 'retail', preferred_terminology: { service_point: 'cashiers', customer: 'customers' } })
    const user = userEvent.setup()
    renderWithProviders(<OnboardingPage />, { route: '/onboarding?replay=1' })
    expect(await screen.findByText('Onboarding replay')).toBeInTheDocument()
    expect(screen.getByRole('heading', { name: 'Welcome to NovaQ' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Cancel' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Skip intro' }))
    expect(screen.getByLabelText('Operation type')).toHaveValue('retail')
    expect(screen.getByRole('button', { name: 'Save preferences' })).toBeEnabled()
  })

  it('restores typed labels when replaying custom terminology', async () => {
    getStatusMock.mockResolvedValue({
      completed: true,
      operation_type: 'other',
      preferred_terminology: {
        service_point: 'other',
        customer: 'other',
        operation_label: 'Laundry shop',
        service_point_label: 'Washers',
        service_point_label_singular: 'Washer',
        customer_label: 'Guests',
        customer_label_singular: 'Guest',
      },
    })
    const user = userEvent.setup()
    renderWithProviders(<OnboardingPage />, { route: '/onboarding?replay=1' })
    await user.click(await screen.findByRole('button', { name: 'Skip intro' }))
    expect(screen.getByLabelText('Name your operation')).toHaveValue('Laundry shop')
    expect(screen.getAllByLabelText('Name for more than one').map((input) => (input as HTMLInputElement).value)).toEqual(['Washers', 'Guests'])
    expect(screen.getAllByLabelText('Name for one').map((input) => (input as HTMLInputElement).value)).toEqual(['Washer', 'Guest'])
    expect(screen.getByText('Your terms: Washers · Guests')).toBeInTheDocument()
  })
})
