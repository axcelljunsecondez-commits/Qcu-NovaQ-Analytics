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

function renderCalculator(route = '/calculator', lang: 'en' | 'tl' = 'en') {
  return renderWithProviders(
    <Routes>
      <Route path="/calculator" element={<><QuickCalculatorPage /><Address /></>} />
      <Route path="/tools/calculator" element={<QuickCalculatorPage />} />
    </Routes>,
    { route, lang },
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
  it.each([false, true])('discloses Erlang-A workload for main and neighbors (signed in: %s)', async (signedIn) => {
    if (signedIn) meMock.mockResolvedValue({ user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' } })
    // Unchanged Erlang-A responses for synthetic 20/h, 6/h/counter, theta=1/h.
    const erlang: Record<number, Partial<AnalysisOut>> = {
      1: { L: 15.000274825134113, Lq: 14.00032979016208, W: 2.5001832268300035, Wq: 2.333516560163337, rho_effective: 0.9999450349720332, abandonment_rate: 0.700016489508104 },
      2: { L: 10.08525207873604, Lq: 8.1023024944844, W: 0.847664186626492, Wq: 0.6809975199598253, rho_effective: 0.9914747921258199, abandonment_rate: 0.40511512472422 },
      3: { L: 6.241481324030335, Lq: 3.489777588836849, W: 0.3780373860870034, Wq: 0.2113707194203367, rho_effective: 0.9172345783978287, abandonment_rate: 0.17448887944184246 },
    }
    const response = async (_model: string, body: { c: number }): Promise<AnalysisOut> => ({
      rho: 20 / (body.c * 6), L: null, Lq: null, W: null, Wq: null, stable: true, error: null,
      metric_basis: 'workload_per_served_throughput',
      ...erlang[body.c],
    })
    runGuestMock.mockImplementation(response)
    runAnalysisMock.mockImplementation(response)
    const user = userEvent.setup()
    renderCalculator(`${signedIn ? '/tools/calculator' : '/calculator'}?situation=leaving`)
    await waitFor(() => expect(screen.getByRole('link', { name: "Start an Analysis" })).toHaveAttribute('href', signedIn ? '/analyses/new' : '/login?next=%2Fanalyses%2Fnew'))
    await fill(user, { "Customer Arriving per hour": '20', "Customer Served per hour (one counter only)": '6', "Current Open Counter": '2', 'Average patience before leaving (minutes)': '60' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    const card = await screen.findByTestId('calculator-wait')
    expect(card).toHaveTextContent('Queue workload per customer served')
    expect(card).toHaveTextContent('40.8599 min')
    expect(card).not.toHaveTextContent('Average wait in line')
    // Inspect the tooltip via its supported hover interaction. First-click
    // focus/toggle behavior belongs to unchanged InfoTip, not this caption repair.
    await user.hover(within(card).getByRole('button', { name: 'About: Queue workload per customer served' }))
    expect(screen.getByRole('tooltip')).toHaveTextContent("This is not an individual customer's average wait.")
    const lines = within(screen.getByTestId('calculator-meaning')).getAllByRole('listitem')
    expect(lines).toHaveLength(3)
    for (const line of lines) {
      expect(line).toHaveTextContent('queue workload per customer served')
      expect(line).toHaveTextContent("not an individual customer's average wait")
      expect(line).not.toHaveTextContent('customers wait about')
    }
    const used = signedIn ? runAnalysisMock : runGuestMock
    expect(used.mock.calls.map(([model, body]) => [model, body.c, body.theta])).toEqual([['erlang_a', 2, 1], ['erlang_a', 1, 1], ['erlang_a', 3, 1]])
    expect(signedIn ? runGuestMock : runAnalysisMock).not.toHaveBeenCalled()
  })

  it('discloses the same Erlang-A meaning in Filipino', async () => {
    runGuestMock.mockResolvedValue({ ...MMC[3], Wq: 0.6809975199598253, metric_basis: 'workload_per_served_throughput', rho_effective: 0.9914747921258199, abandonment_rate: 0.40511512472422 })
    const user = userEvent.setup()
    renderCalculator('/calculator?situation=leaving', 'tl')
    await fill(user, { "Dumarating na customer kada oras": '20', "Bilang ng kostumer na pinagsilbihan kada oras (isang counter lamang)": '6', "Kasalukuyang bukas na Counter": '2', 'Karaniwang pasensiya bago umalis (minuto)': '60' })
    await user.click(screen.getByRole('button', { name: 'Kalkulahin' }))
    const card = await screen.findByTestId('calculator-wait')
    expect(card).toHaveTextContent('Queue workload bawat naserbisyuhang customer')
    expect(card).toHaveTextContent('40.8599')
    expect(screen.getByTestId('calculator-meaning')).toHaveTextContent('Hindi ito ang average na oras ng paghihintay ng isang customer.')
  })

  it.each(['variable', 'limited'] as const)('keeps the ordinary wait meaning for %s service', async (situation) => {
    // Independent limits: M/D/1 PK wait = 1/8 h; a loss-only M/M/1/1 has no queue.
    runGuestMock.mockImplementation(async (_model: string, body: { c: number }): Promise<AnalysisOut> => {
      if (situation === 'limited') return { rho: 1 / 3, L: 1 / 3, Lq: 0, W: 1 / 4, Wq: 0, stable: true, error: null, blocking_probability: 1 / 3 }
      return body.c === 1
        ? { rho: 1 / 2, L: 3 / 4, Lq: 1 / 4, W: 3 / 8, Wq: 1 / 8, stable: true, error: null }
        : { rho: 1 / 4, L: 31 / 60, Lq: 1 / 60, W: 31 / 120, Wq: 1 / 120, stable: true, error: null }
    })
    const user = userEvent.setup()
    renderCalculator(`/calculator?situation=${situation}`)
    await fill(user, { "Customer Arriving per hour": '2', "Customer Served per hour (one counter only)": '4', "Current Open Counter": '1' })
    if (situation === 'variable') await fill(user, { "Time Consistency (in minutes)": '0' })
    else await fill(user, { 'Most customers inside at once': '1' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    const card = await screen.findByTestId('calculator-wait')
    expect(card).toHaveTextContent('Average wait in line')
    expect(card).toHaveTextContent(situation === 'variable' ? '7.5 min' : '0 min')
    expect(screen.getByTestId('calculator-meaning')).not.toHaveTextContent('workload')
  })

  it('lets a guest calculate with c - 1, c and c + 1 from three real calls', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await fill(user, { "Customer Arriving per hour": '40', "Customer Served per hour (one counter only)": '15', "Current Open Counter": '3' })
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
    expect(screen.getByRole('link', { name: "Start an Analysis" })).toHaveAttribute('href', '/login?next=%2Fanalyses%2Fnew')
  })

  it('uses the account endpoint when signed in', async () => {
    meMock.mockResolvedValue({ user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' } })
    const user = userEvent.setup()
    renderCalculator('/tools/calculator')
    await screen.findByRole('link', { name: "Start an Analysis" })
    await waitFor(() => expect(screen.getByRole('link', { name: "Start an Analysis" })).toHaveAttribute('href', '/analyses/new'))
    await fill(user, { "Customer Arriving per hour": '40', "Customer Served per hour (one counter only)": '15', "Current Open Counter": '3' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(runAnalysisMock).toHaveBeenCalledTimes(3))
    expect(runGuestMock).not.toHaveBeenCalled()
  })

  it('never asks for 0 counters, and one counter is M/M/1', async () => {
    runGuestMock.mockImplementation(async () => MMC[3])
    const user = userEvent.setup()
    renderCalculator()
    await fill(user, { "Customer Arriving per hour": '10', "Customer Served per hour (one counter only)": '15', "Current Open Counter": '1' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    await waitFor(() => expect(runGuestMock).toHaveBeenCalledTimes(2))
    expect(runGuestMock.mock.calls.map(([model, body]) => [model, body.c])).toEqual([['mm1', 1], ['mmc', 2]])
  })

  it('shows no wait when counters cannot keep up', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await fill(user, { "Customer Arriving per hour": '40', "Customer Served per hour (one counter only)": '15', "Current Open Counter": '2' })
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
    await fill(user, { "Customer Arriving per hour": '40', "Customer Served per hour (one counter only)": '15', "Current Open Counter": '3' })
    await user.click(screen.getByRole('button', { name: 'Calculate' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Too many requests. Try again later.')
  })

  it('opens every explanation by keyboard and closes it with Escape', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await screen.findByLabelText("Customer Arriving per hour")
    const about = screen.getByRole('button', { name: 'About: Customer Arriving per hour' })
    for (let presses = 0; presses < 12 && document.activeElement !== about; presses += 1) await user.tab()
    expect(about).toHaveFocus()
    expect(screen.getByRole('tooltip')).toHaveTextContent("λ (lambda): Number of customers arriving within an hour. (on Average)")
    expect(about).toHaveAccessibleDescription("λ (lambda): Number of customers arriving within an hour. (on Average)")
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('tooltip')).not.toBeInTheDocument()
  })

  it('keeps the situation in the address and asks for its own inputs', async () => {
    const user = userEvent.setup()
    renderCalculator()
    await user.click(await screen.findByRole('tab', { name: "Line Leaving Rates" }))
    expect(screen.getByTestId('address')).toHaveTextContent('/calculator?situation=leaving')
    expect(screen.getByRole('tab', { name: "Line Leaving Rates" })).toHaveAttribute('aria-selected', 'true')
    expect(screen.getByLabelText('Average patience before leaving (minutes)')).toBeInTheDocument()
    await user.click(screen.getByRole('tab', { name: "Limited Queue Capacity" }))
    expect(screen.getByLabelText('Most customers inside at once')).toBeInTheDocument()
    expect(screen.getByLabelText("Time Consistency in minutes. (Optional)")).toBeInTheDocument()
  })
})
