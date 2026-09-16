import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../test/test-utils'
import { AnalysisCurrentPage } from './AnalysisCurrentPage'

const listDatasetsMock = vi.fn()
const getCurrentMock = vi.fn()

vi.mock('../api/analyses', () => ({
  listAnalysisDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getCurrentMock(...args),
}))

beforeEach(() => {
  listDatasetsMock.mockReset()
  getCurrentMock.mockReset()
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
    expect(screen.getByText('Peak Hour').parentElement).toHaveTextContent('11-12')
    expect(screen.getByText('Lean Hour').parentElement).toHaveTextContent('09-10')
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
})
