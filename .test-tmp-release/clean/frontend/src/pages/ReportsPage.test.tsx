import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { ReportsPage } from './ReportsPage'

const listDatasetsMock = vi.fn()
const listScenariosMock = vi.fn()
const fetchReportMock = vi.fn()
const createObjectURLMock = vi.fn()
const revokeObjectURLMock = vi.fn()
let clickSpy: ReturnType<typeof vi.spyOn>

vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  getDataset: vi.fn(),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))

vi.mock('../api/scenarios', () => ({
  listScenarios: (...args: unknown[]) => listScenariosMock(...args),
  createScenario: vi.fn(),
}))

vi.mock('../api/reports', async () => {
  const actual = await vi.importActual<typeof import('../api/reports')>('../api/reports')
  return { ...actual, fetchReport: (...args: unknown[]) => fetchReportMock(...args) }
})

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const dataset = {
  id: 1,
  name: 'sample',
  source_filename: 'sample.csv',
  source_format: 'csv',
  row_count: 1,
  validation: { ok: true, message: 'Input data is valid.' },
  created_at: '2026-08-01T10:00:00Z',
  normalized: [{ time: '08:00-09:00', lambda: 30, mu: 12, c: 3 }],
}

const scenario = {
  id: 1,
  dataset_id: 1,
  name: 'Plan A',
  settings: {},
  results: { results: [] },
  created_at: '2026-08-02T10:00:00Z',
}

beforeEach(() => {
  listDatasetsMock.mockReset()
  listScenariosMock.mockReset()
  fetchReportMock.mockReset()
  listDatasetsMock.mockResolvedValue({ datasets: [dataset] })
  listScenariosMock.mockResolvedValue({ scenarios: [scenario] })
  fetchReportMock.mockResolvedValue(new Blob(['pdf'], { type: 'application/pdf' }))
  createObjectURLMock.mockReset().mockReturnValue('blob:report')
  revokeObjectURLMock.mockReset()
  clickSpy = vi.spyOn(HTMLAnchorElement.prototype, 'click').mockImplementation(() => {})
  vi.stubGlobal('URL', {
    ...URL,
    createObjectURL: createObjectURLMock,
    revokeObjectURL: revokeObjectURLMock,
  })
})

afterEach(() => {
  clickSpy.mockRestore()
  vi.unstubAllGlobals()
})

describe('ReportsPage', () => {
  it('shows dataset and scenario source cards with PDF/Excel buttons', async () => {
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const datasetCard = await screen.findByTestId('report-card-datasets')
    const scenarioCard = await screen.findByTestId('report-card-scenarios')
    expect(await within(datasetCard).findByRole('option', { name: 'sample' })).toBeInTheDocument()
    expect(within(scenarioCard).getByRole('option', { name: 'Plan A' })).toBeInTheDocument()
    expect(within(datasetCard).getByRole('button', { name: 'Download PDF' })).toBeInTheDocument()
    expect(within(datasetCard).getByRole('button', { name: 'Download Excel' })).toBeInTheDocument()
    expect(within(scenarioCard).getByRole('button', { name: 'Download PDF' })).toBeInTheDocument()
    expect(within(scenarioCard).getByRole('button', { name: 'Download Excel' })).toBeInTheDocument()
  })

  it('downloads a dataset PDF as a blob and triggers the anchor download', async () => {
    const user = userEvent.setup()
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const datasetCard = await screen.findByTestId('report-card-datasets')
    await within(datasetCard).findByRole('option', { name: 'sample' })
    await user.click(within(datasetCard).getByRole('button', { name: 'Download PDF' }))
    await waitFor(() => {
      expect(fetchReportMock).toHaveBeenCalledWith('datasets', 1, 'pdf')
    })
    await waitFor(() => {
      expect(createObjectURLMock).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(clickSpy).toHaveBeenCalled()
    })
    await waitFor(() => {
      expect(revokeObjectURLMock).toHaveBeenCalled()
    })
    expect(await screen.findByText('Report downloaded.')).toBeInTheDocument()
  })

  it('downloads a scenario Excel via the scenario source card', async () => {
    const user = userEvent.setup()
    const downloadSpy = vi.spyOn(HTMLAnchorElement.prototype, 'download', 'set')
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    const scenarioCard = await screen.findByTestId('report-card-scenarios')
    await within(scenarioCard).findByRole('option', { name: 'Plan A' })
    await user.click(within(scenarioCard).getByRole('button', { name: 'Download Excel' }))
    await waitFor(() => {
      expect(fetchReportMock).toHaveBeenCalledWith('scenarios', 1, 'excel')
    })
    await waitFor(() => {
      expect(downloadSpy).toHaveBeenCalledWith('novaq_scenarios_1.xlsx')
    })
    downloadSpy.mockRestore()
  })

  it('shows the empty state when no datasets or scenarios exist', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [] })
    listScenariosMock.mockResolvedValue({ scenarios: [] })
    renderWithProviders(<ReportsPage />, { route: '/reports' })
    expect(await screen.findByText('No data available for reports.')).toBeInTheDocument()
  })
})
