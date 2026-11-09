import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { AnalysisProjectOut } from '../../api/types'
import type { WorkflowEvidence } from '../../api/workflow'
import { renderWithProviders } from '../../test/test-utils'
import en from '../../../public/locales/en/translation.json'
import tl from '../../../public/locales/tl/translation.json'
import { ReplayView } from './ReplayView'
import { buildContext } from './simulationContext'

// A6 Replay of a per-date separate-lines Current run (C-PD-C): one GET per (job, date), cached; 404 W3, 409 W2.
// All values are SYNTHETIC.

const getCurrentDay = vi.hoisted(() => vi.fn())
vi.mock('../../api/workflow', async (importOriginal) => ({
  ...(await importOriginal<typeof import('../../api/workflow')>()),
  getCurrentDay: (...args: unknown[]) => getCurrentDay(...args),
}))

const D1 = '2000-01-03'
const D2 = '2000-01-04'
const emptyTrace = { trace: [], trace_hours: 1, total_hours: 2, event_count: 0, truncated: false, abandonment_supported: false, segments: [] }
const segment = (date: string, queue: string) => ({
  segment_id: 's1', time: `${date} s1 UTC`, queue_id: queue, server_id: `server:${queue}`, lambda: 2, mu: 10, c: 1,
  selected_model: 'Parallel M/G/1', simulation_supported: true, error: null, queue_structure: 'separate' as const,
  initial_queue_depth: 0, final_queue_depth: 0, date,
})
const day = (date: string) => ({
  date, arrivals: 1, served: 1, waiting_at_close: 0, in_service_at_close: 0, customer_conservation: true, day_hours: 2,
  rows_digest: 'a'.repeat(64), trace_digest: 'b'.repeat(64), event_count: 3, truncated: false,
})
const compact = {
  ...emptyTrace, results: [], execution: 'current_per_date_days_compact', days: [day(D1), day(D2)], zero_arrival_lane_periods: [], seed_used: 7,
}
function detail(date: string) {
  return {
    ...emptyTrace, execution: 'current_per_date_day_detail', date, job_id: 31, days: [day(date)], zero_arrival_lane_periods: [],
    segments: [segment(date, 'c1')],
    trace: [
      { t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_len_after: 1, queue_id: 'c1', date },
      { t: 0.1, type: 'service_start', segment_id: 's1', customer_id: 1, server_id: 'server:c1', queue_len_after: 0, queue_id: 'c1', date },
      { t: 0.2, type: 'service_end', segment_id: 's1', customer_id: 1, server_id: 'server:c1', queue_len_after: 0, queue_id: 'c1', date },
    ],
    event_count: 3,
  }
}

function renderReplay(result: unknown, { route = '/simulation/replay?analysis=7', lang = 'en' as 'en' | 'tl' } = {}) {
  const analysis = {
    id: 7, name: 'Checkout',
    queue_setup: {
      queue_structure: 'separate_queues', event_period_basis: 'per_date', queue_ids: ['c1'], breaks: [],
      segments: [{ id: 's1', start_time: '08:00', end_time: '09:00', active_queue_ids: null }, { id: 's2', start_time: '09:00', end_time: '10:00', active_queue_ids: null }],
    },
  } as unknown as AnalysisProjectOut
  const workflow = {
    analysis_id: 7, selection: null, scenario: null, des: null,
    des_current: { id: 31, kind: 'workflow_des_current', status: 'completed', params: { analysis_id: 7, seed: null }, result, created_at: '2026-11-02T00:00:00Z', finished_at: null },
    mc: null, validation: null, mc_current: null, validation_current: null, decision: null, decision_stale: false,
  } as unknown as WorkflowEvidence
  return renderWithProviders(<ReplayView context={buildContext(7, analysis, workflow)} run="current" />, { route, lang })
}

const httpError = (status: number) => Object.assign(new Error(`HTTP ${status}`), { response: { status, data: { detail: 'PLACEHOLDER: server text' } } })

beforeEach(() => {
  getCurrentDay.mockReset()
})

describe('Replay of a compact per-date Current run (A6)', () => {
  it('says it is loading, then plays the chosen date from its own day detail', async () => {
    let resolve: (value: unknown) => void = () => {}
    getCurrentDay.mockReturnValue(new Promise((done) => { resolve = done }))
    renderReplay(compact)
    expect(screen.getByTestId('current-day-loading')).toHaveTextContent(en['common.loading'])
    expect(screen.getByTestId('current-day-loading')).toHaveAttribute('role', 'status')
    expect(screen.getByText(en['simulation.one_run_notice_separate'])).toBeInTheDocument()
    expect(getCurrentDay).toHaveBeenCalledWith(7, D1)
    resolve(detail(D1))
    expect(await screen.findByTestId('replay-period')).toHaveTextContent(`${D1} · 08:00 - 10:00`)
    expect(screen.queryByTestId('current-day-loading')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Date')).toHaveValue(D1)
  })

  it.each([
    [404, 'en', en['simulation.current_day_not_found']],
    [409, 'en', en['simulation.current_day_mismatch']],
    [500, 'en', en['errors.server']],
    [429, 'en', en['errors.server']],
    [404, 'tl', tl['simulation.current_day_not_found']],
    [409, 'tl', tl['simulation.current_day_mismatch']],
    [500, 'tl', tl['errors.server']],
  ] as const)('shows %s in %s with its own message, never the server text', async (status, lang, message) => {
    getCurrentDay.mockRejectedValue(httpError(status))
    renderReplay(compact, { lang })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent(message)
    expect(alert).not.toHaveTextContent('PLACEHOLDER')
    expect(getCurrentDay).toHaveBeenCalledTimes(1)  // no retry
    expect(screen.queryByTestId('replay-period')).not.toBeInTheDocument()
  })

  it('fetches each date once: a revisited date comes from the cache', async () => {
    const user = userEvent.setup()
    getCurrentDay.mockImplementation(async (_analysis: number, date: string) => detail(date))
    renderReplay(compact)
    expect(await screen.findByTestId('replay-period')).toHaveTextContent(D1)
    await user.selectOptions(screen.getByLabelText('Date'), D2)
    await waitFor(() => expect(screen.getByTestId('replay-period')).toHaveTextContent(D2))
    await user.selectOptions(screen.getByLabelText('Date'), D1)
    await waitFor(() => expect(screen.getByTestId('replay-period')).toHaveTextContent(D1))
    expect(getCurrentDay.mock.calls).toEqual([[7, D1], [7, D2]])
  })

  it('starts each date from its own beginning: the playback is keyed by job and date (K-CPD-4)', async () => {
    const user = userEvent.setup()
    getCurrentDay.mockImplementation(async (_analysis: number, date: string) => detail(date))
    renderReplay(compact)
    expect(await screen.findByTestId('replay-period')).toHaveTextContent(D1)
    // Both dates cached, so switching shows the other date at once (no loading state in between).
    await user.selectOptions(screen.getByLabelText('Date'), D2)
    await waitFor(() => expect(screen.getByTestId('replay-period')).toHaveTextContent(D2))
    await user.selectOptions(screen.getByLabelText('Date'), D1)
    await waitFor(() => expect(screen.getByTestId('replay-period')).toHaveTextContent(D1))
    fireEvent.change(screen.getByLabelText(en['simulation.live_event_position']), { target: { value: '0.15' } })
    expect(screen.getByLabelText(en['simulation.live_event_position'])).toHaveValue('0.15')
    await user.selectOptions(screen.getByLabelText('Date'), D2)
    await waitFor(() => expect(screen.getByTestId('replay-period')).toHaveTextContent(D2))
    expect(screen.getByLabelText(en['simulation.live_event_position'])).toHaveValue('0')
    expect(getCurrentDay).toHaveBeenCalledTimes(2)
  })

  it('asks for the date in the address', async () => {
    getCurrentDay.mockImplementation(async (_analysis: number, date: string) => detail(date))
    renderReplay(compact, { route: `/simulation/replay?analysis=7&date=${D2}` })
    expect(await screen.findByTestId('replay-period')).toHaveTextContent(D2)
    expect(getCurrentDay.mock.calls).toEqual([[7, D2]])
  })
})

describe('Replay of a one-date per-date Current run (A6)', () => {
  it('plays the stored trace as before and never asks for a day detail', () => {
    const one = { ...detail(D1), execution: 'current_per_date_days', results: [] }
    renderReplay(one)
    expect(screen.getByText(en['simulation.one_run_notice_separate'])).toBeInTheDocument()
    expect(screen.getByTestId('replay-period')).toHaveTextContent(`${D1} s1 UTC`)
    expect(screen.queryByLabelText('Date')).not.toBeInTheDocument()
    expect(getCurrentDay).not.toHaveBeenCalled()
  })
})
