import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import type { QueueSetup } from '../api/types'
import { AnalysisSetupPage } from './AnalysisSetupPage'

const getAnalysisMock = vi.fn()
const patchMock = vi.fn()
const uploadMock = vi.fn()
const previewMock = vi.fn()
const downloadMock = vi.fn()

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: (...args: unknown[]) => patchMock(...args),
  listAnalysisDatasets: vi.fn(async () => ({ datasets: [] })),
  getAnalysisCurrent: vi.fn(),
  uploadAnalysisDataset: (...args: unknown[]) => uploadMock(...args),
  previewAnalysisDataset: (...args: unknown[]) => previewMock(...args),
  downloadSetupWorkbook: (...args: unknown[]) => downloadMock(...args),
}))

vi.mock('../api/templates', () => ({
  getTemplateGuide: vi.fn(async () => ({ structure: 'separate_queues', schema: 'events', columns: [], example_rows: [], field_guide: [], accepted_aliases: {} })),
  downloadTemplate: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const unknownSetup: QueueSetup = {
  queue_structure: 'unknown', fixed_server_count: null, staffing_varies_by_period: false, capacity_mode: 'unknown',
  total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null, segments: [],
  separate_queue_closure_policy: 'drain_existing', queue_ids: [], breaks: [],
}

const derived: QueueSetup = {
  ...unknownSetup,
  queue_structure: 'separate_queues',
  staffing_varies_by_period: true,
  capacity_mode: 'unlimited',
  abandonment_mode: 'not_modeled',
  queue_ids: ['cashier_1', 'cashier_2'],
  segments: [
    { id: '05:00-06:00', start_time: '05:00:00', end_time: '06:00:00', active_queue_ids: ['cashier_1'] },
    { id: '06:00-07:00', start_time: '06:00:00', end_time: '07:00:00', active_queue_ids: ['cashier_1', 'cashier_2'] },
  ],
  breaks: [
    { queue_id: 'cashier_1', scheduled_start_time: '05:30:00', duration_minutes: 15 },
    { queue_id: 'cashier_2', scheduled_start_time: '06:15:00', duration_minutes: 30, break_name: 'Lunch' },
  ],
  event_period_basis: 'representative_day',
}

function preview(overrides: Record<string, unknown> = {}) {
  return {
    mode: 'multi_sheet',
    derived_setup: derived,
    saved_setup: unknownSetup,
    diff: [{ field: 'queue_ids', saved: [], derived: derived.queue_ids }],
    needs_confirmation: false,
    staff: [
      { row: 2, queue_id: 'cashier_1', shift_start: '05:00', shift_end: '07:00' },
      { row: 3, queue_id: 'cashier_2', shift_start: '06:00', shift_end: '07:00' },
    ],
    breaks: [
      { row: 2, queue_id: 'cashier_1', break_name: null, start: '05:30', minutes: 15, label: 'Break 1' },
      { row: 3, queue_id: 'cashier_2', break_name: 'Lunch', start: '06:15', minutes: 30, label: 'Lunch' },
    ],
    errors: [],
    ...overrides,
  }
}

function analysisWith(setup: QueueSetup) {
  return { analysis: { id: 7, name: 'NovaMart', service_type: null, location_label: null, queue_setup: setup,
    setup_status: 'ready', archived_at: null, created_at: '2026-09-18T00:00:00Z', updated_at: '2026-09-18T00:00:00Z' } }
}

const dataset = { dataset: { id: 3, validation: { ok: true, message: 'Input data is valid.' } } }

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
    </Routes>,
    { route: '/analyses/7/setup' },
  )
}

async function uploadFile(name: string) {
  const user = userEvent.setup()
  renderPage()
  const input = await screen.findByLabelText('Upload Data')
  const file = new File(['x'], name)
  await user.upload(input, file)
  await user.click(screen.getByRole('button', { name: 'Upload and process' }))
  return { user, file }
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue(analysisWith(unknownSetup))
  patchMock.mockReset().mockResolvedValue({ analysis: { id: 7 } })
  uploadMock.mockReset().mockResolvedValue(dataset)
  previewMock.mockReset().mockResolvedValue(preview())
  downloadMock.mockReset().mockResolvedValue(undefined)
})

describe('three-sheet upload', () => {
  it('fills an unknown Setup directly and shows what NovaQ read', async () => {
    const { file } = await uploadFile('novamart.xlsx')
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file, { applySetup: true }))
    const summary = await screen.findByRole('region', { name: "Here's what NovaQ read from your file" })
    expect(within(summary).getByText('cashier_1, cashier_2')).toBeInTheDocument()
    expect(within(summary).getByText('cashier_1: 05:00–07:00')).toBeInTheDocument()
    expect(within(summary).getByText('05:00-06:00: cashier_1')).toBeInTheDocument()
    expect(within(summary).getByText('cashier_1 · Break 1 · 05:30 · 15 min')).toBeInTheDocument()
    expect(within(summary).getByText('cashier_2 · Lunch · 06:15 · 30 min')).toBeInTheDocument()
    expect(within(summary).getByText('Representative day (average all observed dates)')).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Replace Setup and upload' })).not.toBeInTheDocument()
  })

  it('keeps a different saved Setup until the user confirms', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith({ ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['lane_a'] }))
    previewMock.mockResolvedValue(preview({ needs_confirmation: true }))
    const { user, file } = await uploadFile('novamart.xlsx')
    const confirm = (await screen.findByText('This file would change your saved Setup')).closest('.alert') as HTMLElement
    expect(within(confirm).getByText('Queue IDs')).toBeInTheDocument()
    expect(uploadMock).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Replace Setup and upload' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file, { applySetup: true }))
  })

  it('cancelling the confirmation uploads nothing', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith({ ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['lane_a'] }))
    previewMock.mockResolvedValue(preview({ needs_confirmation: true }))
    const { user } = await uploadFile('novamart.xlsx')
    await user.click(await screen.findByRole('button', { name: 'Cancel' }))
    expect(screen.queryByText('This file would change your saved Setup')).not.toBeInTheDocument()
    expect(uploadMock).not.toHaveBeenCalled()
  })

  it('lists every reading error and uploads nothing', async () => {
    previewMock.mockResolvedValue(preview({ derived_setup: null, diff: [], errors: [
      'Staff sheet row 2: shift_start must be before shift_end.',
      'Breaks sheet row 3: minutes must be a positive whole number.',
    ] }))
    await uploadFile('novamart.xlsx')
    const alert = await screen.findByRole('alert')
    expect(within(alert).getByText('Staff sheet row 2: shift_start must be before shift_end.')).toBeInTheDocument()
    expect(within(alert).getByText('Breaks sheet row 3: minutes must be a positive whole number.')).toBeInTheDocument()
    expect(uploadMock).not.toHaveBeenCalled()
  })

  it('uploads legacy workbooks and CSV files exactly as before', async () => {
    previewMock.mockResolvedValue({ mode: 'legacy' })
    const { file } = await uploadFile('events.xlsx')
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file))
  })

  it('never previews a CSV upload', async () => {
    const { file } = await uploadFile('events.csv')
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file))
    expect(previewMock).not.toHaveBeenCalled()
  })
})

describe('setup workbook export and break labels', () => {
  it('downloads the setup workbook for separate queues only', async () => {
    const user = userEvent.setup()
    getAnalysisMock.mockResolvedValue(analysisWith(derived))
    renderPage()
    await user.click(await screen.findByRole('button', { name: 'Download setup workbook' }))
    expect(downloadMock).toHaveBeenCalledWith(7)
  })

  it('hides the export for a non-separate Setup', async () => {
    renderPage()
    await screen.findByLabelText('Upload Data')
    expect(screen.queryByRole('button', { name: 'Download setup workbook' })).not.toBeInTheDocument()
  })

  it('labels breaks by name, else Break n in time order per queue', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith({ ...derived, breaks: [
      { queue_id: 'cashier_1', scheduled_start_time: '06:30:00', duration_minutes: 15 },
      { queue_id: 'cashier_1', scheduled_start_time: '05:30:00', duration_minutes: 15 },
      { queue_id: 'cashier_2', scheduled_start_time: '06:15:00', duration_minutes: 30, break_name: 'Lunch' },
    ] }))
    renderPage()
    const editor = (await screen.findByRole('heading', { name: 'Server break schedule' })).closest('.card') as HTMLElement
    expect(within(editor).getAllByTestId('break-label').map((node) => node.textContent)).toEqual(['Break 2', 'Break 1', 'Lunch'])
  })
})

describe('time segment checks', () => {
  // A saved Setup returns times as HH:MM:SS; new or edited segments hold HH:MM.
  async function renderSaved() {
    getAnalysisMock.mockResolvedValue(analysisWith(derived))
    const user = userEvent.setup()
    renderPage()
    await screen.findByRole('button', { name: 'Add time segment' })
    return user
  }

  it('saves touching segments when saved and new times use different formats', async () => {
    const user = await renderSaved()
    await user.click(screen.getByRole('button', { name: 'Add time segment' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    expect(screen.queryByText('Time segments cannot overlap.')).not.toBeInTheDocument()
  })

  it('still blocks segments that really overlap', async () => {
    const user = await renderSaved()
    await user.click(screen.getByRole('button', { name: 'Add time segment' }))
    fireEvent.change(screen.getByLabelText('Start time', { selector: '#segment-start-2' }), { target: { value: '06:30' } })
    fireEvent.change(screen.getByLabelText('End time', { selector: '#segment-end-2' }), { target: { value: '07:30' } })
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText('Time segments cannot overlap.')).toBeInTheDocument()
    expect(patchMock).not.toHaveBeenCalled()
  })
})
