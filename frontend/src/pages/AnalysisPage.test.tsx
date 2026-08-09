import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { AnalysisPage } from './AnalysisPage'

const runAnalysisMock = vi.fn()

vi.mock('../api/analysis', () => ({
  runAnalysis: (...args: unknown[]) => runAnalysisMock(...args),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const mmcResult = {
  rho: 0.8333333333333334,
  L: 6.011235955056181,
  Lq: 3.511235955056181,
  W: 0.20037453183520604,
  Wq: 0.1170411985018727,
  stable: true,
  error: null,
}

beforeEach(() => {
  runAnalysisMock.mockReset()
})

describe('AnalysisPage', () => {
  it('renders tabs for all six models with translated labels', () => {
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    for (const label of ['M/M/1', 'M/M/c', 'M/G/c', 'M/M/K', 'M/G/K', 'Erlang-A']) {
      expect(screen.getByRole('button', { name: label })).toBeInTheDocument()
    }
  })

  it('defaults to M/M/1 with lambda and mu fields and calls the API on run', async () => {
    runAnalysisMock.mockResolvedValue({
      rho: 0.5,
      L: 1,
      Lq: 0.5,
      W: 0.066,
      Wq: 0.033,
      stable: true,
      error: null,
    })
    const user = userEvent.setup()
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    await user.type(screen.getByLabelText('λ'), '30')
    await user.type(screen.getByLabelText('μ'), '60')
    await user.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => {
      expect(runAnalysisMock).toHaveBeenCalledWith(
        'mm1',
        expect.objectContaining({ lambda: 30, mu: 60 }),
      )
    })
  })

  it('renders result metric cards for rho, Lq and Wq', async () => {
    runAnalysisMock.mockResolvedValue(mmcResult)
    const user = userEvent.setup()
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    await user.click(screen.getByRole('button', { name: 'M/M/c' }))
    await user.type(screen.getByLabelText('λ'), '30')
    await user.type(screen.getByLabelText('μ'), '12')
    await user.clear(screen.getByLabelText('c'))
    await user.type(screen.getByLabelText('c'), '3')
    await user.click(screen.getByRole('button', { name: 'Run analysis' }))
    expect(await screen.findByText('83.33%')).toBeInTheDocument()
    expect(screen.getByText('3.51')).toBeInTheDocument()
    expect(screen.getByText('0.12')).toBeInTheDocument()
  })

  it('shows the error message for an unstable system', async () => {
    runAnalysisMock.mockResolvedValue({
      rho: 2.5,
      L: null,
      Lq: null,
      W: null,
      Wq: null,
      stable: false,
      error: 'Unstable system: lambda must be less than mu for M/M/1.',
    })
    const user = userEvent.setup()
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    await user.type(screen.getByLabelText('λ'), '30')
    await user.type(screen.getByLabelText('μ'), '12')
    await user.click(screen.getByRole('button', { name: 'Run analysis' }))
    expect(
      await screen.findByText('Unstable system: lambda must be less than mu for M/M/1.'),
    ).toBeInTheDocument()
  })

  it('Erlang-A tab adds a theta input and passes it to the API', async () => {
    runAnalysisMock.mockResolvedValue(mmcResult)
    const user = userEvent.setup()
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    await user.click(screen.getByRole('button', { name: 'Erlang-A' }))
    await user.type(screen.getByLabelText('θ'), '1.5')
    await user.type(screen.getByLabelText('λ'), '30')
    await user.type(screen.getByLabelText('μ'), '12')
    await user.clear(screen.getByLabelText('c'))
    await user.type(screen.getByLabelText('c'), '3')
    await user.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => {
      expect(runAnalysisMock).toHaveBeenCalledWith(
        'erlang_a',
        expect.objectContaining({ theta: 1.5 }),
      )
    })
  })

  it('M/M/K tab adds a K input and passes it to the API', async () => {
    runAnalysisMock.mockResolvedValue(mmcResult)
    const user = userEvent.setup()
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    await user.click(screen.getByRole('button', { name: 'M/M/K' }))
    await user.type(screen.getByLabelText('K'), '10')
    await user.type(screen.getByLabelText('λ'), '30')
    await user.type(screen.getByLabelText('μ'), '12')
    await user.clear(screen.getByLabelText('c'))
    await user.type(screen.getByLabelText('c'), '3')
    await user.click(screen.getByRole('button', { name: 'Run analysis' }))
    await waitFor(() => {
      expect(runAnalysisMock).toHaveBeenCalledWith(
        'mmck',
        expect.objectContaining({ K: 10 }),
      )
    })
  })

  it('renders a 422 validation error message', async () => {
    runAnalysisMock.mockRejectedValue({
      response: { status: 422, data: { detail: 'Model mm1 requires parameters: mu.' } },
    })
    const user = userEvent.setup()
    renderWithProviders(<AnalysisPage />, { route: '/analysis' })
    await user.type(screen.getByLabelText('λ'), '30')
    await user.type(screen.getByLabelText('μ'), '12')
    await user.click(screen.getByRole('button', { name: 'Run analysis' }))
    expect(
      await screen.findByText('Model mm1 requires parameters: mu.'),
    ).toBeInTheDocument()
  })
})
