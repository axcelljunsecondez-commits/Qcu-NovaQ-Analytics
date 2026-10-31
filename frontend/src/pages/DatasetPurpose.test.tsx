import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeQueryClient, renderWithProviders } from '../test/test-utils'
import type { DatasetOut, QueueSetup } from '../api/types'
import { currentDatasetId, isForPlanning } from '../lib/datasets'
import { AnalysisSetupPage } from './AnalysisSetupPage'
import { DatasetsPage } from './DatasetsPage'

const getAnalysisMock = vi.fn()
const listAnalysisDatasetsMock = vi.fn()
const getAnalysisCurrentMock = vi.fn()
const uploadMock = vi.fn()
const previewMock = vi.fn()
const listDatasetsMock = vi.fn()

vi.mock('../api/analyses', () => ({
  previewSharedAggregateDataset: vi.fn(async () => ({ mode: 'declined', reasons: [] })),
  applySharedAggregateDataset: vi.fn(),
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: vi.fn(),
  listAnalysisDatasets: (...args: unknown[]) => listAnalysisDatasetsMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getAnalysisCurrentMock(...args),
  uploadAnalysisDataset: (...args: unknown[]) => uploadMock(...args),
  previewAnalysisDataset: (...args: unknown[]) => previewMock(...args),
  downloadSetupWorkbook: vi.fn(),
}))
vi.mock('../api/datasets', () => ({
  listDatasets: (...args: unknown[]) => listDatasetsMock(...args),
  uploadDataset: vi.fn(),
  deleteDataset: vi.fn(),
}))
vi.mock('../api/templates', () => ({
  getTemplateGuide: vi.fn(async () => ({ structure: 'shared_queue', schema: 'aggregate', columns: [], example_rows: [], field_guide: [], accepted_aliases: {} })),
  downloadTemplate: vi.fn(),
}))
vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

const shared: QueueSetup = {
  queue_structure: 'shared_queue', fixed_server_count: 2, staffing_varies_by_period: false, capacity_mode: 'unlimited',
  total_system_capacity: null, abandonment_mode: 'not_modeled', patience_rate_per_hour: null, segments: [],
  separate_queue_closure_policy: 'drain_existing', queue_ids: [], breaks: [],
}

function dataset(id: number, purpose: 'planning' | 'review', isCurrent: boolean | null | undefined): DatasetOut {
  return {
    id, analysis_id: 7, name: `file ${id}`, source_filename: `f${id}.csv`, source_format: 'csv', row_count: 1,
    validation: { ok: true, message: 'Input data is valid.' }, created_at: '2026-10-09T00:00:00Z', normalized: null,
    purpose, is_current: isCurrent,
  }
}

function renderSetup(queryClient = makeQueryClient()) {
  return renderWithProviders(
    <Routes><Route path="/analyses/:analysisId/data" element={<AnalysisSetupPage />} /></Routes>,
    { route: '/analyses/7/data', queryClient },
  )
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue({ analysis: { id: 7, name: 'A', service_type: null, location_label: null, queue_setup: shared,
    setup_status: 'ready', archived_at: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' } })
  listAnalysisDatasetsMock.mockReset().mockResolvedValue({ datasets: [] })
  getAnalysisCurrentMock.mockReset().mockRejectedValue(new Error('not needed'))
  uploadMock.mockReset().mockResolvedValue({ dataset: dataset(9, 'review', false) })
  previewMock.mockReset()
  listDatasetsMock.mockReset()
})

describe('currentDatasetId and isForPlanning', () => {
  it('follow the server, not the list order', () => {
    expect(currentDatasetId([dataset(3, 'review', false), dataset(2, 'planning', true)])).toBe(2)
    expect(currentDatasetId([dataset(3, 'review', false)])).toBeNull()
    expect(currentDatasetId([])).toBeNull()
    expect(currentDatasetId(undefined)).toBeNull()
  })

  it('keep the pre-B10 meaning when the server sends no is_current', () => {
    expect(currentDatasetId([dataset(3, 'planning', undefined), dataset(2, 'planning', undefined)])).toBe(3)
    expect(isForPlanning({ ...dataset(1, 'planning', true), purpose: undefined })).toBe(true)
    expect(isForPlanning(dataset(1, 'review', false))).toBe(false)
  })
})

describe('What the upload is for (B10, D16)', () => {
  it('asks with nothing preselected and blocks the upload until answered', async () => {
    const user = userEvent.setup()
    renderSetup()
    await user.upload(await screen.findByLabelText('Upload Data'), new File(['x'], 'week.csv'))
    expect(screen.queryByRole('button', { name: 'Upload and process' })).not.toBeInTheDocument()
    expect(uploadMock).not.toHaveBeenCalled()
    expect(previewMock).not.toHaveBeenCalled()
    expect(screen.getByText('Choose what this file is for before uploading.')).toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: /Review only/ }))
    expect(screen.getByRole('button', { name: 'Upload and process' })).toBeEnabled()
  })

  it('uploads a review-only workbook as it is: no Setup preview, no Setup change, plans kept', async () => {
    const queryClient = makeQueryClient()
    queryClient.setQueryData(['workflow', 7], { kept: true })
    queryClient.setQueryData(['scenarios', 7], { scenarios: [{ id: 1, evidence_status: 'CURRENT' }] })
    const invalidate = vi.spyOn(queryClient, 'invalidateQueries')
    const user = userEvent.setup()
    renderSetup(queryClient)
    await user.click(await screen.findByRole('radio', { name: /Review only/ }))
    const file = new File(['x'], 'week.xlsx')
    await user.upload(screen.getByLabelText('Upload Data'), file)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file, { purpose: 'review' }))
    expect(previewMock).not.toHaveBeenCalled()
    expect(await screen.findByRole('status')).toHaveTextContent('Saved as a review-only file. Your plans, simulations and checks are unchanged.')
    expect(queryClient.getQueryData(['workflow', 7])).toEqual({ kept: true })
    expect(queryClient.getQueryData(['scenarios', 7])).toEqual({ scenarios: [{ id: 1, evidence_status: 'CURRENT' }] })
    expect(invalidate).toHaveBeenCalledWith({ queryKey: ['datasets', 7] })
    expect(invalidate).not.toHaveBeenCalledWith({ queryKey: ['current', 7] })
    expect(screen.getByRole('radio', { name: /Review only/ })).not.toBeChecked()
  })

  it('a planning upload still drops cached evidence as before', async () => {
    uploadMock.mockResolvedValue({ dataset: dataset(10, 'planning', true) })
    const queryClient = makeQueryClient()
    queryClient.setQueryData(['workflow', 7], { stale: true })
    const user = userEvent.setup()
    renderSetup(queryClient)
    await user.click(await screen.findByRole('radio', { name: /Use for planning/ }))
    const file = new File(['x'], 'week.csv')
    await user.upload(screen.getByLabelText('Upload Data'), file)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file))
    await waitFor(() => expect(queryClient.getQueryData(['workflow', 7])).toBeUndefined())
  })

  it('reads results from the current planning file even when a newer review file exists', async () => {
    listAnalysisDatasetsMock.mockResolvedValue({ datasets: [dataset(12, 'review', false), dataset(11, 'planning', true)] })
    getAnalysisCurrentMock.mockResolvedValue({ selected_model: 'M/M/c', explanations: [] })
    const queryClient = makeQueryClient()
    renderSetup(queryClient)
    await waitFor(() => expect(getAnalysisCurrentMock).toHaveBeenCalled())
    expect(queryClient.getQueryCache().find({ queryKey: ['current', 7, 11] })).toBeDefined()
    expect(queryClient.getQueryCache().find({ queryKey: ['current', 7, 12] })).toBeUndefined()
  })

  it('says so when the analysis has only review files, without asking for results', async () => {
    listAnalysisDatasetsMock.mockResolvedValue({ datasets: [dataset(12, 'review', false)] })
    renderSetup()
    expect(await screen.findByText('You have only review-only files. Upload a file for planning to make plans.')).toBeInTheDocument()
    expect(getAnalysisCurrentMock).not.toHaveBeenCalled()
  })
})

describe('Uploaded files list (Settings)', () => {
  it('shows what each file is for and which planning file is current', async () => {
    listDatasetsMock.mockResolvedValue({ datasets: [dataset(3, 'review', false), dataset(2, 'planning', true), dataset(1, 'planning', false)] })
    renderWithProviders(<DatasetsPage />)
    const rows = await screen.findAllByRole('row')
    const text = rows.slice(1).map((row) => within(row).getAllByRole('cell').map((cell) => cell.textContent).join('|'))
    expect(text[0]).toContain('Review only')
    expect(text[1]).toContain('Planning (current)')
    expect(text[2]).toContain('Planning')
    expect(text[2]).not.toContain('current')
  })
})
