import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import type { AnalysisOut } from '../api/types'
import { renderWithProviders } from '../test/test-utils'
import { QuickCalculatorPage } from './QuickCalculatorPage'

const meMock = vi.fn()
const runAnalysisMock = vi.fn()
const runGuestMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(async () => ({ user: null })),
  logout: vi.fn(async () => ({})),
}))

vi.mock('../api/analysis', () => ({
  runAnalysis: (...args: unknown[]) => runAnalysisMock(...args),
  runGuestCalculator: (...args: unknown[]) => runGuestMock(...args),
}))

// NovaQ's mmc for λ 40/h, μ 15/h (spec §7.12 board example, VERIFIED by execution there).
const MMC: Record<number, AnalysisOut> = {
  2: { rho: 1.3333333333333333, L: null, Lq: null, W: null, Wq: null, stable: false,
    error: 'Unstable system: lambda must be less than c * mu for M/M/c.' },
  3: { rho: 0.8888888888888888, L: 9.046728971962612, Lq: 6.380062305295946, W: 0.2261682242990653,
    Wq: 0.15950155763239865, stable: true, error: null },
  4: { rho: 0.6666666666666666, L: 3.4234, Lq: 0.7568, W: 0.0856, Wq: 0.018921, stable: true, error: null },
}

function Address() {
  const location = useLocation()
  return <output data-testid="address">{location.pathname}{location.search}</output>
}

function renderCalculator(route = '/calculator') {
  return renderWithProviders(
    <Routes>
      <Route path="/calculator" element={<><QuickCalculatorPage /><Address /></>} />
      <Route path="/tools/calculator" element={<QuickCalculatorPage />} />
    </Routes>,
    { route },
  )
}

async function fill(user: ReturnType<typeof userEvent.setup>, values: Record<string, string>) {
  for (const [label, value] of Object.entries(values)) {
    const input = await screen.findByLabelText(label)
    await user.clear(input)
    await user.type(input, value)
  }
}

beforeEach(() => {
  meMock.mockReset()
  meMock.mockRejectedValue(Object.assign(new Error('Not signed in'), { status: 401 }))
  runAnalysisMock.mockReset()
  runGuestMock.mockReset()
  runGuestMock.mockImplementation(async (_model: string, body: { c: number }) => MMC[body.c])
  runAnalysisMock.mockImplementation(async (_model: string, body: { c: number }) => MMC[body.c])
})

describe('Quick calculator (U9 + B2)', () => {
  it('lets a guest calculate with c - 1, c and c + 1 from three real calls', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await fill(user, { 'Customers arriving per hour': '40', 'Customers one counter serves per hour': '15', 'Counters open': '3' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(runGuestMock).toHaveBeenCalledTimes(3))
    expect(runGuestMock.mock.calls.map(([model, body]) => [model, body.c])).toEqual([['mmc', 3], ['mmc', 2], ['mmc', 4]])
    expect(runAnalysisMock).not.toHaveBeenCalled()
    expect(await screen.findByTestId('calculator-wait')).toHaveTextContent('9.5701 min')
    expect(screen.getByTestId('calculator-busy')).toHaveTextContent('88.8889%')
    expect(screen.getByTestId('calculator-waiting')).toHaveTextContent('6.3801')
    expect(screen.getByTestId('calculator-keep_up')).toHaveTextContent('Yes')
    expect(screen.getByText('Model: M/M/c')).toBeInTheDocument()
    const lines = within(screen.getByTestId('calculator-meaning')).getAllByRole('listitem').map((item) => item.textContent)
    expect(lines).toEqual([
      'With 3 counter(s), customers wait about 9.5701 minutes in line on average, and counters are busy 88.8889% of the time.',
      'With 2 counter(s): cannot keep up — the line keeps growing.',
      'With 4 counter(s), customers wait about 1.1353 minutes in line on average, and counters are busy 66.6667% of the time.',
    ])
    expect(screen.getByRole('link', { name: 'Start an analysis' })).toHaveAttribute('href', '/login?next=%2Fanalyses%2Fnew')
  })

  it('uses the account endpoint when signed in', async () => {
    meMock.mockResolvedValue({ user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' } })
    const user = userEvent.setup()
    renderCalculator('/tools/calculator')
    await screen.findByRole('link', { name: 'Start an analysis' })
    await waitFor(() => expect(screen.getByRole('link', { name: 'Start an analysis' })).toHaveAttribute('href', '/analyses/new'))
    await fill(user, { 'Customers arriving per hour': '40', 'Customers one counter serves per hour': '15', 'Counters open': '3' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(runAnalysisMock).toHaveBeenCalledTimes(3))
    expect(runGuestMock).not.toHaveBeenCalled()
  })

  it('never asks for 0 counters, and one counter is M/M/1', async () => {
    runGuestMock.mockImplementation(async () => MMC[3])
    const user = userEvent.setup()
    renderCalculator()
    await fill(user, { 'Customers arriving per hour': '10', 'Customers one counter serves per hour': '15', 'Counters open': '1' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(runGuestMock).toHaveBeenCalledTimes(2))
    expect(runGuestMock.mock.calls.map(([model, body]) => [model, body.c])).toEqual([['mm1', 1], ['mmc', 2]])
  })

  it('shows no wait when counters cannot keep up', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await fill(user, { 'Customers arriving per hour': '40', 'Customers one counter serves per hour': '15', 'Counters open': '2' })
    runGuestMock.mockImplementation(async (_model: string, body: { c: number }) => MMC[body.c] ?? MMC[2])
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    expect(await screen.findByTestId('calculator-wait')).toHaveTextContent('—')
    expect(screen.getByTestId('calculator-keep_up')).toHaveTextContent('No')
    expect(within(screen.getByTestId('calculator-meaning')).getAllByRole('listitem')[0])
      .toHaveTextContent('With 2 counter(s): cannot keep up — the line keeps growing.')
  })

  it('names missing inputs without calling NovaQ, and shows a refusal from the server', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await user.click(await screen.findByRole('button', { name: 'Calculate' }))
    expect(screen.getByText('Enter 0 or more customers per hour.')).toBeInTheDocument()
    expect(screen.getByText('Enter a whole number, 1 or more.')).toBeInTheDocument()
    expect(runGuestMock).not.toHaveBeenCalled()
    runGuestMock.mockRejectedValue({ isAxiosError: true, response: { status: 429, data: { detail: 'Too many requests. Try again later.' } } })
    await fill(user, { 'Customers arriving per hour': '40', 'Customers one counter serves per hour': '15', 'Counters open': '3' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many requests. Try again later.')
  })

  it('opens every explanation by keyboard and closes it with Escape', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await screen.findByLabelText('Customers arriving per hour')
    const about = screen.getByRole('button', { name: 'About: Customers arriving per hour' })
    for (let presses = 0; presses < 12 && document.activeElement !== about; presses += 1) await user.tab()
    expect(about).toHaveFocus()
    expect(screen.getByRole('tooltip')).toHaveTextContent('λ (lambda): the average number of customers who arrive in one hour.')
    expect(about).toHaveAccessibleDescription('λ (lambda): the average number of customers who arrive in one hour.')
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('keeps the situation in the address and asks for its own inputs', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await user.click(await screen.findByRole('tab', { name: 'Some people leave' }))
    expect(screen.getByTestId('address')).toHaveTextContent('/calculator?situation=leaving')
    expect(screen.getByRole('tab', { name: 'Some people leave' })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Average patience before leaving (minutes)')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: 'Limited waiting space' }))
    expect(screen.getByLabelText('Most customers inside at once')).toBeInTheDocument()
    expect(screen.getByLabelText('Typical spread of service time (minutes, optional)')).toBeInTheDocument()
  })
})
