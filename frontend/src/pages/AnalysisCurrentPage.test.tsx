import { describe, expect, it, vi, beforeEach } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import { renderWithProviders } from '../test/test-utils'
import { AnalysisCurrentPage } from './AnalysisCurrentPage'

const listDatasetsMock = vi.fn()
const getCurrentMock = vi.fn()

vi.mock('../api/analyses', () => ({
  listAnalysisDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getCurrentMock(...args),
}))

const getObservedWaitMock = vi.fn()

vi.mock('../api/workflow', () => ({
  getObservedWait: (...args: unknown[]) => getObservedWaitMock(...args),
}))

beforeEach(() => {
  listDatasetsMock.mockReset()
  getCurrentMock.mockReset()
  getObservedWaitMock.mockReset()
})

describe('AnalysisCurrentPage', () => {
  it('maps KPI fields to the backend contract and picks the true peak hour', async () => {
    listDatasetsMock.mockResolvedValue({
      datasets: [{ id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 3, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }],
    })

    getCurrentMock.mockResolvedValue({
      analysis: {
        id: 7,
        name: 'North checkout',
        service_type: 'checkout',
        location_label: 'North',
        queue_setup: {
          queue_structure: 'shared_queue',
          fixed_server_count: 2,
          staffing_varies_by_period: false,
          capacity_mode: 'unlimited',
          total_system_capacity: null,
          abandonment_mode: 'not_modeled',
          patience_rate_per_hour: null,
        },
        setup_status: 'ready',
        archived_at: null,
        created_at: '2026-09-01T00:00:00Z',
        updated_at: '2026-09-01T00:00:00Z',
      },
      dataset: { id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 3, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' },
      selected_model: 'M/M/c',
      rows: [
        { time: '09-10', lambda: 10, Wq: 0.1, rho: 0.3, model: 'M/M/c', status: 'Lean' },
        { time: '11-12', lambda: 60, Wq: 0.5, rho: 0.9, model: 'M/M/c', status: 'Peak' },
        { time: '17-18', lambda: 45, Wq: 0.3, rho: 0.8, model: 'M/M/c', status: 'Peak' },
      ],
      kpis: {
        avg_waiting_time: 0.25,
        avg_utilization: 0.74,
      },
      explanations: [],
    })

    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })

    expect(await screen.findByText('15.0 minutes')).toBeInTheDocument()
    expect(screen.getByText('30.0 minutes')).toBeInTheDocument()
    expect(screen.getByText('74%')).toBeInTheDocument()
    expect(screen.getByText('Utilization').parentElement).toHaveTextContent('74%')
    expect(screen.getByText('Busiest Period').parentElement).toHaveTextContent('11-12')
    expect(screen.getByText('Leanest Period').parentElement).toHaveTextContent('09-10')
    expect(screen.getByText('Status Legend')).toBeInTheDocument()
    expect(document.querySelector('.status-dot-peak')).toBeInTheDocument()
    expect(document.querySelector('.status-dot-normal')).toBeInTheDocument()
    expect(document.querySelector('.status-dot-lean')).toBeInTheDocument()
    expect(screen.getByRole('table', { name: 'Arrival-rate data for every computed interval' })).toBeInTheDocument()
    expect(screen.queryByText(/High during peak periods/)).not.toBeInTheDocument()
  })

  it('shows one row per queue with its queue label for separate analyses', async () => {
    listDatasetsMock.mockResolvedValue({
      datasets: [{ id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 2, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }],
    })
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues' } },
      dataset: { id: 99 },
      selected_model: 'Parallel M/G/1',
      rows: [
        { time: '08:00-09:00', queue_id: 'north', lambda: 4, mu: 6, c: 1, Wq: 0.05, rho: 0.7, model: 'Parallel M/G/1', status: 'Normal' },
        { time: '08:00-09:00', queue_id: 'south', lambda: 5, mu: 6, c: 1, Wq: 0.08, rho: 0.8, model: 'Parallel M/G/1', status: 'Normal' },
      ],
      kpis: { avg_waiting_time: 0.065, avg_utilization: 0.75 },
      explanations: [],
    })
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const table = await screen.findByRole('table', { name: 'Complete current-state analytical results by interval' })
    expect(table).toHaveTextContent('Service line')
    expect(table).toHaveTextContent('north')
    expect(table).toHaveTextContent('south')
  })

  function mockSeparateCurrent() {
    listDatasetsMock.mockResolvedValue({
      datasets: [{ id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 3, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }],
    })
    const row = (time: string, queue_id: string) => ({ time, queue_id, queue_structure: 'separate_queues', lambda: 4, mu: 6, c: 1, Wq: 0.05, rho: 0.7, model: 'Parallel M/G/1', status: 'Normal' })
    const explanation = (time: string, queue_id: string) => ({ time, queue_id, selected_model: 'Parallel M/G/1', selection_reason: `reason ${time} ${queue_id}`, operational_facts: [], measured_characteristics: [], model_assumptions: [] })
    // The south lane opens at 09:00, so 08:00-09:00 has no south row.
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues' } },
      dataset: { id: 99 },
      selected_model: 'Parallel M/G/1',
      rows: [row('08:00-09:00', 'north'), row('09:00-10:00', 'north'), row('09:00-10:00', 'south')],
      kpis: { avg_waiting_time: 0.05, avg_utilization: 0.7 },
      explanations: [explanation('08:00-09:00', 'north'), explanation('09:00-10:00', 'north'), explanation('09:00-10:00', 'south')],
    })
  }

  async function resultsSection() {
    const table = await screen.findByRole('table', { name: 'Complete current-state analytical results by interval' })
    return { table, section: table.closest('section')! }
  }

  it('filters results and explanations by period and service line', async () => {
    mockSeparateCurrent()
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const { table, section } = await resultsSection()
    expect(within(table).getAllByRole('rowheader')).toHaveLength(3)
    expect(within(section).getByRole('status')).toHaveTextContent('Showing 3 of 3')
    // The explanation card starts collapsed.
    const explanationCard = screen.getByText('Model Selection Explanation').closest('details')!
    expect(explanationCard).not.toHaveAttribute('open')

    fireEvent.change(within(section).getByRole('combobox', { name: 'Time' }), { target: { value: '09:00-10:00' } })
    fireEvent.change(within(section).getByRole('combobox', { name: 'Service line' }), { target: { value: 'south' } })
    const rows = within(table).getAllByRole('rowheader')
    expect(rows).toHaveLength(1)
    expect(rows[0].parentElement).toHaveTextContent('09:00-10:00')
    expect(rows[0].parentElement).toHaveTextContent('south')
    expect(within(section).getByRole('status')).toHaveTextContent('Showing 1 of 3')
    // Both lists share the filter, so the explanation card shrinks too.
    expect(within(explanationCard).getByText('Showing 1 of 3')).toBeInTheDocument()
    expect(screen.getByText('reason 09:00-10:00 south')).toBeInTheDocument()
    expect(screen.queryByText('reason 08:00-09:00 north')).not.toBeInTheDocument()
  })

  it('shows a no-match message instead of an empty table when the filters select nothing', async () => {
    mockSeparateCurrent()
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const { section } = await resultsSection()
    fireEvent.change(within(section).getByRole('combobox', { name: 'Time' }), { target: { value: '08:00-09:00' } })
    fireEvent.change(within(section).getByRole('combobox', { name: 'Service line' }), { target: { value: 'south' } })
    expect(screen.queryByRole('table', { name: 'Complete current-state analytical results by interval' })).not.toBeInTheDocument()
    expect(within(section).getByRole('status')).toHaveTextContent('Showing 0 of 3')
    expect(screen.getAllByText('No intervals match the selected time and service line.')).toHaveLength(2)
  })

  it('shows no filter controls when there is one period and one service line', async () => {
    listDatasetsMock.mockResolvedValue({
      datasets: [{ id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 1, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }],
    })
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'shared_queue' } },
      dataset: { id: 99 },
      selected_model: 'M/M/c',
      rows: [{ time: '09-10', lambda: 10, mu: 12, c: 3, Wq: 0.1, rho: 0.3, model: 'M/M/c', status: 'Lean' }],
      kpis: { avg_waiting_time: 0.1, avg_utilization: 0.3 },
      explanations: [],
    })
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    await resultsSection()
    expect(screen.queryByRole('combobox')).not.toBeInTheDocument()
    expect(document.querySelector('.period-filter')).not.toBeInTheDocument()
  })

  it('omits the queue column for shared analyses', async () => {
    listDatasetsMock.mockResolvedValue({
      datasets: [{ id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 1, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }],
    })
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'shared_queue' } },
      dataset: { id: 99 },
      selected_model: 'M/M/c',
      rows: [
        { time: '09-10', lambda: 10, mu: 12, c: 3, Wq: 0.1, rho: 0.3, model: 'M/M/c', status: 'Lean' },
      ],
      kpis: { avg_waiting_time: 0.1, avg_utilization: 0.3 },
      explanations: [],
    })
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const table = await screen.findByRole('table', { name: 'Complete current-state analytical results by interval' })
    expect(table).not.toHaveTextContent('Service line')
  })

  it('names the busiest period by combined arrival rate, not the loudest single queue', async () => {
    listDatasetsMock.mockResolvedValue({
      datasets: [{ id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 3, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }],
    })
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues' } },
      dataset: { id: 99 },
      selected_model: 'Parallel M/G/1',
      rows: [
        { time: '05:00-06:00', queue_id: 'Q1', queue_structure: 'separate_queues', lambda: 10, mu: 12, c: 1, Wq: 0.2, rho: 0.83, model: 'Parallel M/G/1', status: 'Peak' },
        { time: '06:00-07:00', queue_id: 'Q1', queue_structure: 'separate_queues', lambda: 6, mu: 12, c: 1, Wq: 0.05, rho: 0.5, model: 'Parallel M/G/1', status: 'Lean' },
        { time: '06:00-07:00', queue_id: 'Q2', queue_structure: 'separate_queues', lambda: 6, mu: 12, c: 1, Wq: 0.05, rho: 0.5, model: 'Parallel M/G/1', status: 'Lean' },
      ],
      kpis: { avg_waiting_time: 0.1, avg_utilization: 0.6 },
      explanations: [],
    })
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    expect(await screen.findByText('Busiest Period')).toBeInTheDocument()
    expect(screen.getByText('Busiest Period').parentElement).toHaveTextContent('06:00-07:00')
    expect(screen.getByText('Leanest Period').parentElement).toHaveTextContent('05:00-06:00')
  })
})

describe('AnalysisCurrentPage modeled vs observed wait', () => {
  const eventValidation = {
    ok: true,
    message: 'ok',
    derived_statistics: [{ time: '05:00-06:00', queue_id: 'Q1', duration_minutes: 60, mean_waiting_time_hours: 0.5 }],
  }

  function mockCurrent(validation: Record<string, unknown>) {
    const dataset = { id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'events.csv', source_format: 'csv', row_count: 2, validation, normalized: null, created_at: '2026-09-01T00:00:00Z' }
    listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: 'separate_queues' } },
      dataset,
      selected_model: 'Parallel M/G/1',
      rows: [
        { time: '05:00-06:00', queue_id: 'Q1', queue_structure: 'separate_queues', lambda: 2, mu: 5, c: 1, Wq: 0.1, rho: 0.4, model: 'Parallel M/G/1', status: 'Lean' },
        { time: '06:00-07:00', queue_id: 'Q1', queue_structure: 'separate_queues', lambda: 3, mu: 5, c: 1, Wq: 0.2, rho: 0.6, model: 'Parallel M/G/1', status: 'Normal' },
      ],
      kpis: { avg_waiting_time: 0.16, avg_utilization: 0.5 },
      explanations: [],
    })
  }

  function observed(flagged: boolean) {
    return {
      analysis_id: 7, dataset_id: 99, available: true, ratio: 2, min_gap_minutes: 5,
      flagged_any: flagged,
      day_modeled_wait: 0.16, day_observed_wait: flagged ? 0.6 : 0.17,
      periods: [
        { time: '05:00-06:00', modeled_wait: 0.1, observed_wait: flagged ? 0.5 : 0.11, flagged },
        { time: '06:00-07:00', modeled_wait: 0.2, observed_wait: null, flagged: false },
      ],
    }
  }

  const banner = 'Observed waits are much longer than cashier workload explains. Results describe the modeled system; check how waits were recorded.'

  it('labels the modeled wait and shows observed waits with the day banner when flagged', async () => {
    mockCurrent(eventValidation)
    getObservedWaitMock.mockResolvedValue(observed(true))
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    expect(await screen.findByText(banner)).toBeInTheDocument()
    expect(getObservedWaitMock).toHaveBeenCalled()
    expect(screen.getAllByText('Modeled current wait').length).toBeGreaterThan(0)
    expect(screen.queryByText('Average Wait Time')).not.toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Modeled vs observed wait by period' })
    expect(table).toHaveTextContent('Observed wait')
    expect(table).toHaveTextContent('30.0')
    expect(table).toHaveTextContent('6.0')
    expect(table).toHaveTextContent('Much longer than modeled')
    // A period without an observed wait shows a dash, never zero.
    expect(within(table).getByRole('rowheader', { name: '06:00-07:00' }).parentElement).toHaveTextContent('—')
  })

  it('hides the banner when no period is flagged', async () => {
    mockCurrent(eventValidation)
    getObservedWaitMock.mockResolvedValue(observed(false))
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const table = await screen.findByRole('table', { name: 'Modeled vs observed wait by period' })
    expect(table).toHaveTextContent('6.6')
    expect(table).not.toHaveTextContent('Much longer than modeled')
    expect(screen.queryByText(banner)).not.toBeInTheDocument()
  })

  it('shows no observed wait, flag or banner for aggregate uploads', async () => {
    mockCurrent({ ok: true, message: 'ok' })
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    expect(await screen.findByText('Average Wait Time')).toBeInTheDocument()
    expect(getObservedWaitMock).not.toHaveBeenCalled()
    expect(screen.queryByText('Observed wait')).not.toBeInTheDocument()
    expect(screen.queryByText(banner)).not.toBeInTheDocument()
  })
})

describe('AnalysisCurrentPage charts', () => {
  const dataset = { id: 99, analysis_id: 7, name: 'Dataset', source_filename: 'data.csv', source_format: 'csv', row_count: 7, validation: { ok: true, message: 'ok' }, normalized: null, created_at: '2026-09-01T00:00:00Z' }
  const lane = (time: string, queue_id: unknown, lambda: number, rho: unknown, status = 'Normal') => ({ time, queue_id, queue_structure: 'separate_queues', lambda, mu: 6, c: 1, Wq: 0.05, rho, model: 'Parallel M/G/1', status })

  function mockRows(rows: Record<string, unknown>[], queueStructure = 'separate_queues') {
    listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
    getCurrentMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { queue_structure: queueStructure } },
      dataset,
      selected_model: rows[0]?.model,
      rows,
      kpis: { avg_waiting_time: 0.05, avg_utilization: 0.6 },
      explanations: [],
    })
  }

  function bodyRows(table: HTMLElement) {
    return within(table).getAllByRole('row').slice(1).map((row) => Array.from(row.children).map((cell) => cell.textContent))
  }

  // Q2 has one finite ρ (the others are null and non-numeric); Q3 has none.
  const separateRows = [
    lane('05:00-06:00', 'Q1', 2.4285714285714284, 0.5, 'Lean'),
    lane('05:00-06:00', 'Q2', 2.4285714285714284, 0.9, 'Peak'),
    lane('06:00-07:00', 'Q1', 3, 0.6),
    lane('06:00-07:00', 'Q2', 4, null),
    lane('06:00-07:00', 'Q3', 0.5, null),
    lane('07:00-08:00', 'Q1', 2.5, 0.7142857142857143, 'Peak'),
    lane('07:00-08:00', 'Q2', 1.5, 'not a number'),
  ]

  it('sums separate-queue arrivals once per period without repeating hour labels', async () => {
    mockRows(separateRows)
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const chart = await screen.findByRole('img', { name: 'Customer arrivals per hour (all cashiers combined)' })
    expect(within(chart).getAllByText(/^\d\d:00-\d\d:00$/).map((node) => node.textContent)).toEqual(['05:00-06:00', '06:00-07:00', '07:00-08:00'])
    // Four decimals, except a whole number drops its ".0000".
    expect(Array.from(chart.querySelectorAll('.hbar-value')).map((node) => node.textContent)).toEqual(['4.8571', '7.5000', '4'])
    const table = screen.getByRole('table', { name: 'Combined arrival-rate data for every period' })
    expect(bodyRows(table)).toEqual([
      ['05:00-06:00', '4.8571', '2'],
      ['06:00-07:00', '7.5000', '3'],
      ['07:00-08:00', '4', '2'],
    ])
  })

  it('shows cashier workload instead of model distribution for separate queues', async () => {
    mockRows(separateRows)
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const chart = await screen.findByRole('img', { name: 'Cashier workload' })
    expect(screen.queryByRole('heading', { name: 'Queue models used' })).not.toBeInTheDocument()
    expect(Array.from(chart.querySelectorAll('.hbar-label')).map((node) => node.textContent)).toEqual(['Q1', 'Q2'])
    // Q1: mean of 0.5, 0.6 and 0.7142857 = 0.6047619; its peak is the 07:00 row.
    expect(within(chart).getByText('Average 60.4762% · Busiest hour 71.4286%')).toBeInTheDocument()
    expect(within(chart).getByText('Average 90% · Busiest hour 90%')).toBeInTheDocument()
    const legend = document.querySelector('.hbar-legend') as HTMLElement
    expect(within(legend).getAllByRole('listitem').map((item) => item.textContent)).toEqual(['Average utilization', 'Busiest-hour utilization'])
    expect(screen.getByText('Utilization ρ in percent. Scale: 0% to 100%.')).toBeInTheDocument()
    const table = screen.getByRole('table', { name: 'Cashier workload data for every cashier line' })
    expect(bodyRows(table)).toEqual([
      ['Q1', '60.4762%', '71.4286%', '07:00-08:00', 'Peak', '3'],
      ['Q2', '90%', '90%', '05:00-06:00', 'Peak', '1'],
    ])
  })

  it('shows an unavailable state instead of zero when no cashier has a finite utilization', async () => {
    mockRows([
      lane('05:00-06:00', 'Q1', 2, null),
      lane('06:00-07:00', 'Q1', 3, 'NaN'),
      lane('06:00-07:00', null, 3, 0.8),
    ])
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    const heading = await screen.findByRole('heading', { name: 'Cashier workload' })
    const section = heading.closest('section') as HTMLElement
    expect(within(section).getByText('No cashier line has a computed utilization value.')).toBeInTheDocument()
    expect(within(section).queryByRole('img')).not.toBeInTheDocument()
    expect(within(section).queryByText(/%/)).not.toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Queue models used' })).not.toBeInTheDocument()
  })

  it('keeps model distribution and one bar per shared row for shared queues', async () => {
    mockRows([
      { time: '09-10', lambda: 10.123456, mu: 12, c: 2, Wq: 0.1, rho: 0.42, model: 'M/M/c', status: 'Lean' },
      { time: '10-11', lambda: 12, mu: 12, c: 2, Wq: 0.2, rho: 0.5, model: 'M/M/c', status: 'Normal' },
    ], 'shared_queue')
    renderWithProviders(<AnalysisCurrentPage />, { route: '/analyses/7/current' })
    expect(await screen.findByRole('heading', { name: 'Queue models used' })).toBeInTheDocument()
    expect(screen.queryByRole('heading', { name: 'Cashier workload' })).not.toBeInTheDocument()
    const chart = screen.getByRole('img', { name: 'Customer arrivals per hour (all cashiers combined)' })
    expect(Array.from(chart.querySelectorAll('.hbar-value')).map((node) => node.textContent)).toEqual(['10.1235', '12'])
    const table = screen.getByRole('table', { name: 'Arrival-rate data for every computed interval' })
    expect(bodyRows(table)).toEqual([
      ['09-10', '10.1235'],
      ['10-11', '12'],
    ])
  })
})
