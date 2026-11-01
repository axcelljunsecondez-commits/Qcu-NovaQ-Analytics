import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import en from '../../../public/locales/en/translation.json'
import { ContinuousSection } from './ContinuousRun'

// Shared lines: the full-day run (spec 2026-10-29 §7.1, §7.5; owner decisions A6, C3, C4, C6, OD-2).

const listRuns = vi.fn()
const getRun = vi.fn()
const getPlayback = vi.fn()

vi.mock('../../api/continuous', () => ({
  getClosingPolicy: vi.fn(async () => ({ closing_policy: 'DRAIN', choices: [] })),
  putClosingPolicy: vi.fn(),
  getContinuousCompatibility: vi.fn(async () => ({
    closing_policy: 'DRAIN',
    plans: {
      current: { compatible: true, reasons: [], expected_customers_per_day: 13, horizon: { start_minute: 480, end_minute: 600 }, dataset_id: 9, scenario_id: null, scenario_name: null },
      suggested: { compatible: true, reasons: [], expected_customers_per_day: 13, horizon: { start_minute: 480, end_minute: 600 }, dataset_id: 9, scenario_id: 3, scenario_name: 'Plan A' },
    },
    default_replications: 5, default_seed: 42,
    limits: { max_replications: 9, max_expected_customers_per_run: 2900, result_max_bytes: 786432, status: 'provisional_not_production_approved' },
    preview: true, model_scope: 'Preview', verdict: null, verdict_reason: 'No rule.',
  })),
  createContinuousRun: vi.fn(),
  listContinuousRuns: (...args: unknown[]) => listRuns(...args),
  getContinuousRun: (...args: unknown[]) => getRun(...args),
  getContinuousPlayback: (...args: unknown[]) => getPlayback(...args),
}))

const metric = (mean: number | null, min: number | null, max: number | null) => ({ mean, min, max, n: 5, n_undefined: 0, ci_lower: null, ci_upper: null })

function run(id: number, plan: 'current' | 'suggested', waitHours: number, served: number) {
  return {
    evidence: {
      id, kind: 'shared_continuous_preview', created_at: '2026-10-29T00:00:00Z',
      params: { analysis_id: 7, plan, scenario_id: plan === 'suggested' ? 3 : null, dataset_id: 9, replications: 5, seed: 42, closing_policy: 'DRAIN' },
      result: {
        replications: [],
        summary: {
          replications: 5,
          customers: { arrivals: 65, served: 65, unserved: 0, conserved_in_every_replication: true,
            per_replication: { arrivals: metric(13, 10, 16), served: metric(served, 10, 16), unserved: metric(0.4, 0, 1) } },
          waiting_time: { mean_of_replication_means_hours: metric(waitHours, 0.05, 0.1), customer_weighted_mean_hours: { value: waitHours } },
          metrics: { max_queue_in_horizon: metric(3.4, 2, 5), utilization_in_horizon: metric(0.62, 0.5, 0.7) },
        },
        provenance: { replications: 5, seed: 42, closing_policy: 'DRAIN', engine_version: 'v2',
          inputs: { horizon: { start_minute: 480, end_minute: 600 }, demand_periods: [], staffing_segments: [] } },
      },
    },
    setup_matches_current: true, dataset_is_current: true, plan_is_selected: plan === 'suggested' ? true : null,
  }
}

const event = (seq: number, t: number, type: string, queue: number) => ({ seq, t, type, queue_len_after: queue, servers_idle_after: 0, servers_busy_after: 1, servers_draining_after: 0 })
const playback = {
  replication_index: 0,
  playback: {
    events: [event(0, 0, 'server_open', 0), event(1, 0.25, 'arrival', 1), event(2, 0.3, 'arrival', 3), event(3, 0.5, 'service_start', 2),
      event(4, 0.9, 'arrival', 3), event(5, 1.2, 'service_start', 0), event(6, 2, 'closing', 0)],
    closing: { closing_hours: 2, overrun_hours: 0 },
  },
  by_period: [
    { period_id: '08:00-09:00', start_hours: 0, end_hours: 1, arrivals: 3, served: 3, unserved: 0, mean_wait_hours: 0.05 },
    { period_id: '09:00-10:00', start_hours: 1, end_hours: 2, arrivals: 0, served: 0, unserved: 0, mean_wait_hours: null },
    { period_id: '10:00-11:00', start_hours: 2, end_hours: 3, arrivals: 2, served: 2, unserved: 0, mean_wait_hours: 0.1 },
  ],
  preview: true,
}

beforeEach(() => {
  listRuns.mockReset().mockResolvedValue({ runs: [
    { id: 31, plan: 'suggested', replications: 5, seed: 42, closing_policy: 'DRAIN', setup_matches_current: true, dataset_is_current: true, plan_is_selected: true },
    { id: 30, plan: 'current', replications: 5, seed: 42, closing_policy: 'DRAIN', setup_matches_current: true, dataset_is_current: true, plan_is_selected: null },
  ] })
  getRun.mockReset().mockImplementation(async (_analysis: number, id: number) => (id === 31 ? run(31, 'suggested', 0.05, 13) : run(30, 'current', 0.1, 11)))
  getPlayback.mockReset().mockResolvedValue(playback)
})

function renderSection(plan: 'current' | 'suggested' = 'suggested') {
  return renderWithProviders(<ContinuousSection analysisId={7} run={plan} page="results" />)
}

describe('full-day run key results (C3, OD-2)', () => {
  it('shows the hours as a chip in 24-hour "HH:MM - HH:MM"', async () => {
    renderSection()
    const chip = (await screen.findByText('Operating hours: 08:00 - 10:00.')).closest('.hours-chip')
    expect(chip).not.toBeNull()
  })

  it('has the two headline cards and keeps Not served at closing as a card, with ranges and no arrow', async () => {
    renderSection()
    const cards = await screen.findByRole('group', { name: en['continuous.key_results'] })
    await waitFor(() => expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Suggested plan: 3 min'))
    expect(within(cards).getAllByRole('region').map((card) => card.getAttribute('aria-label'))).toEqual(['Average wait', 'Longest Single Line', 'Not served at closing'])
    expect(cards).not.toHaveTextContent('→')
    expect(within(cards).getByRole('region', { name: 'Average wait' })).toHaveTextContent('Current: 6 min (3 min–6 min)')
    expect(within(cards).getByRole('region', { name: 'Longest Single Line' })).toHaveTextContent('Suggested plan: 3.4 (2–5)')
    expect(within(cards).getByRole('region', { name: 'Not served at closing' })).toHaveTextContent('Suggested plan: 0.4 (0–1)')
    expect(screen.queryByRole('button', { name: 'Why these are not the same basis' })).not.toBeInTheDocument()
  })

  it('moves Customer Served into More results as a Current and Suggested pair with ranges', async () => {
    renderSection()
    const served = await screen.findByRole('region', { name: 'Customer Served' })
    expect(served.closest('details')).not.toBeNull()
    expect(served).toHaveTextContent('Current: 11 (10–16)')
    expect(served).toHaveTextContent('Suggested plan: 13 (10–16)')
  })
})

describe('full-day charts (C6)', () => {
  it('draws people waiting with a 0-based whole-number y-axis, clock labels and the closing line', async () => {
    renderSection()
    const chart = await screen.findByTestId('fullday-waiting-chart')
    expect(chart).toHaveAccessibleName('People waiting through the day, up to 3 at once')
    expect(within(screen.getByTestId('fullday-y-axis')).getAllByText(/^\d+$/).map((label) => label.textContent)).toEqual(['0', '1', '2', '3'])
    expect(within(screen.getByTestId('fullday-x-axis')).getAllByText(/^\d\d:\d\d$/).map((label) => label.textContent)).toEqual(['08:00', '09:00', '10:00'])
    expect(chart.querySelector('.cv-close')).not.toBeNull()
    expect(screen.getByText(en['charts.fullday_closing_legend'])).toBeInTheDocument()
    expect(screen.getByTestId('fullday-waiting-take')).toHaveTextContent('Most people waiting at once on day 1: 3, first at 08:18.')
  })

  it('draws average wait by period as one row per period with a labelled gap', async () => {
    const user = userEvent.setup()
    renderSection()
    const chart = await screen.findByTestId('fullday-period-chart')
    expect(chart).toHaveAccessibleName(en['simulation.chart_wait_by_period'])
    const rows = within(chart).getAllByTestId('row-chart-row')
    expect(rows).toHaveLength(playback.by_period.length)
    expect(rows[1]).toHaveTextContent('Unavailable')
    expect(rows[2]).toHaveClass('hl')
    expect(screen.getByTestId('fullday-period-take')).toHaveTextContent('Longest average wait on day 1: 6 min, for customers who arrived in 10:00-11:00.')
    await user.click(rows[0])
    expect(screen.getByTestId('row-chart-readout')).toHaveTextContent('08:00-09:00Average wait: 3 min')
    // The arrival-period note is under details.
    expect(screen.getByText(en['continuous.by_period_hint']).closest('details')).not.toBeNull()
  })

  it('marks the Current run with its own legend entry', async () => {
    renderSection('current')
    const chart = await screen.findByTestId('fullday-period-chart')
    expect(chart.closest('section')).toHaveTextContent('Current')
    expect(chart.querySelector('.cv-m-est')).not.toBeNull()
    expect(chart.querySelector('.cv-m-plan')).toBeNull()
  })
})
