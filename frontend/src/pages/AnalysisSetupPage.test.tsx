import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { act, fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeQueryClient, renderWithProviders } from '../test/test-utils'
import type { QueueSetup } from '../api/types'
import { getAnalysisCurrent, listAnalysisDatasets } from '../api/analyses'
import { AnalysisSetupPage } from './AnalysisSetupPage'

const getAnalysisMock = vi.fn()
const patchMock = vi.fn()
const uploadMock = vi.fn()
const previewMock = vi.fn()
const downloadMock = vi.fn()

vi.mock('../api/analyses', () => ({
  previewSharedAggregateDataset: vi.fn(async () => ({ mode: 'declined', reasons: [] })),
  applySharedAggregateDataset: vi.fn(),
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
  await user.click(screen.getByRole('radio', { name: /Use for planning/ }))
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
  it('fills an unknown Setup directly without a file-read summary', async () => {
    const { file } = await uploadFile('novamart.xlsx')
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file, { applySetup: true }))
    expect(screen.queryByRole('region', { name: "Here's what NovaQ read from your file" })).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Replace Setup and upload' })).not.toBeInTheDocument()
  })

  it('keeps a different saved Setup until the user confirms', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith({ ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['lane_a'] }))
    const savedBreaks = [{ queue_id: 'lane_a', scheduled_start_time: '05:45:00', duration_minutes: 30 }]
    previewMock.mockResolvedValue(preview({
      needs_confirmation: true,
      saved_setup: { ...unknownSetup, queue_ids: ['lane_a'], breaks: savedBreaks },
      diff: [
        { field: 'queue_ids', saved: ['lane_a'], derived: derived.queue_ids },
        { field: 'breaks', saved: savedBreaks, derived: derived.breaks },
      ],
    }))
    const { user, file } = await uploadFile('novamart.xlsx')
    const confirm = (await screen.findByText('This file would change your saved Setup')).closest('.alert') as HTMLElement
    expect(within(confirm).getByText('Queue IDs').closest('li')).toHaveTextContent('lane_a → cashier_1, cashier_2')
    expect(within(confirm).getByText(/lane_a · 05:45/)).toHaveTextContent(/lane_a · 05:45 · 30.*→.*cashier_1 · 05:30 · 15.*cashier_2 · Lunch · 06:15 · 30/)
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

  it('drops this analysis\'s cached workflow result and marks its current dataset stale after an upload', async () => {
    const queryClient = makeQueryClient()
    queryClient.setQueryData(['workflow', 7], { des_current: { params: { dataset_id: 2 } } })
    queryClient.setQueryData(['workflow', 8], { des_current: { params: { dataset_id: 5 } } })
    queryClient.setQueryData(['current', 7], { dataset: { id: 2 } })
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
      </Routes>,
      { route: '/analyses/7/setup', queryClient },
    )
    const file = new File(['x'], 'events.csv')
    await user.upload(await screen.findByLabelText('Upload Data'), file)
    await user.click(screen.getByRole('radio', { name: /Use for planning/ }))
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file))
    await waitFor(() => expect(queryClient.getQueryData(['workflow', 7])).toBeUndefined())
    expect(queryClient.getQueryState(['current', 7])?.isInvalidated).toBe(true)
    // Another analysis's current dataset did not change.
    expect(queryClient.getQueryData(['workflow', 8])).toEqual({ des_current: { params: { dataset_id: 5 } } })
  })
})

describe('setup workbook export and break labels', () => {
  it('hides the setup workbook action for separate queues', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith(derived))
    renderPage()
    await screen.findByRole('heading', { name: /Customer Events/ })
    expect(screen.queryByRole('button', { name: 'Download setup workbook' })).not.toBeInTheDocument()
    expect(downloadMock).not.toHaveBeenCalled()
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

describe('Why This Model?', () => {
  beforeEach(() => {
    vi.mocked(listAnalysisDatasets).mockResolvedValue({ datasets: [{ id: 3 }] } as never)
    vi.mocked(getAnalysisCurrent).mockResolvedValue({
      dataset: { id: 3 },
      selected_model: 'Parallel M/G/1',
      explanations: ['cashier_1', 'cashier_2'].map((queue_id) => ({
        time: '05:00-06:00', queue_id, selected_model: 'Parallel M/G/1', selection_reason: 'Source reason for the model',
        operational_facts: [], measured_characteristics: [], model_assumptions: [],
      })),
    } as never)
  })

  afterEach(() => {
    vi.mocked(listAnalysisDatasets).mockReset().mockImplementation(async () => ({ datasets: [] }))
    vi.mocked(getAnalysisCurrent).mockReset()
  })

  it('shows the actual model and a repeated reason once', async () => {
    renderPage()
    expect(await screen.findByText('Parallel M/G/1')).toBeVisible()
    expect(screen.getByText('Source reason for the model')).toBeVisible()
    expect(screen.queryByText('Show per-period details (2)')).not.toBeInTheDocument()
  })
})

describe('scenario evidence cache (4d)', () => {
  function renderSeeded() {
    const queryClient = makeQueryClient()
    queryClient.setQueryData(['scenarios', 7], { scenarios: [{ id: 1, evidence_status: 'CURRENT' }] })
    queryClient.setQueryData(['scenarios', 8], { scenarios: [{ id: 2, evidence_status: 'CURRENT' }] })
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
      </Routes>,
      { route: '/analyses/7/setup', queryClient },
    )
    return queryClient
  }

  it('drops the cached scenario statuses of this analysis after an upload', async () => {
    const queryClient = renderSeeded()
    const user = userEvent.setup()
    const file = new File(['x'], 'events.csv')
    await user.upload(await screen.findByLabelText('Upload Data'), file)
    await user.click(screen.getByRole('radio', { name: /Use for planning/ }))
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file))
    await waitFor(() => expect(queryClient.getQueryData(['scenarios', 7])).toBeUndefined())
    expect(queryClient.getQueryData(['scenarios', 8])).toEqual({ scenarios: [{ id: 2, evidence_status: 'CURRENT' }] })
  })

  it('drops the cached scenario statuses of this analysis after the Setup is saved', async () => {
    const queryClient = renderSeeded()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(7, expect.objectContaining({ queue_setup: expect.anything() })))
    await waitFor(() => expect(queryClient.getQueryData(['scenarios', 7])).toBeUndefined())
    expect(queryClient.getQueryData(['scenarios', 8])).toEqual({ scenarios: [{ id: 2, evidence_status: 'CURRENT' }] })
  })
})

describe('workflow evidence cache after a Setup save', () => {
  it('drops this analysis\'s cached workflow result and keeps another analysis\'s', async () => {
    const queryClient = makeQueryClient()
    queryClient.setQueryData(['workflow', 7], { des_current: { params: { dataset_id: 2 } } })
    queryClient.setQueryData(['workflow', 8], { des_current: { params: { dataset_id: 5 } } })
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
      </Routes>,
      { route: '/analyses/7/setup', queryClient },
    )
    await user.click(await screen.findByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchMock).toHaveBeenCalledWith(7, expect.objectContaining({ queue_setup: expect.anything() })))
    await waitFor(() => expect(queryClient.getQueryData(['workflow', 7])).toBeUndefined())
    expect(queryClient.getQueryData(['workflow', 8])).toEqual({ des_current: { params: { dataset_id: 5 } } })
  })
})

describe('U10: what the Setup still needs, and the period basis', () => {
  const shared: QueueSetup = { ...unknownSetup, queue_structure: 'shared_queue', capacity_mode: 'unlimited', abandonment_mode: 'not_modeled', event_period_basis: 'per_date' }

  it('does not demand a fixed count before a shared planning file supplies its counts', async () => {
    const incomplete = analysisWith(shared)
    getAnalysisMock.mockResolvedValue({ analysis: { ...incomplete.analysis, setup_status: 'incomplete' } })
    renderPage()
    await screen.findByLabelText('Upload Data')
    expect(screen.queryByTestId('setup-incomplete')).not.toBeInTheDocument()
    expect(screen.getByLabelText('Fixed server count')).toBeInTheDocument()
  })

  it('offers the field beside an upload refusal (F10)', async () => {
    const incomplete = analysisWith(shared)
    getAnalysisMock.mockResolvedValue({ analysis: { ...incomplete.analysis, setup_status: 'incomplete' } })
    uploadMock.mockRejectedValue(Object.assign(new Error('422'), { response: { status: 422, data: { detail: 'Enter the fixed server count before uploading customer-event data.' } } }))
    await uploadFile('records.csv')
    const refusal = await screen.findByRole('alert')
    expect(refusal).toHaveTextContent('Enter the fixed server count before uploading customer-event data.')
    expect(within(refusal).getByRole('button', { name: 'Open Advanced settings' })).toBeInTheDocument()
  })

  it('shows nothing extra for a complete Setup', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith({ ...shared, fixed_server_count: 3 }))
    renderPage()
    await screen.findByLabelText('Upload Data')
    expect(screen.queryByTestId('setup-incomplete')).not.toBeInTheDocument()
  })

  it('says what per-date periods turn off, and asks for the file again after the basis changes (F3)', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith({ ...shared, fixed_server_count: 3 }))
    vi.mocked(listAnalysisDatasets).mockResolvedValue({ datasets: [{ id: 4, name: 'records', is_current: true, purpose: 'planning', validation: { ok: true } }] } as never)
    const user = userEvent.setup()
    renderPage()
    const basis = await screen.findByLabelText('Customer data periods')
    expect(screen.getByText(/the full-day run and break suggestions are not available; choose Representative day for them/)).toBeInTheDocument()
    await user.selectOptions(basis, 'representative_day')
    expect(screen.queryByText(/the full-day run and break suggestions are not available/)).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByText(/upload your planning file again to use the new one/)).toBeInTheDocument()
  })
})

describe('Setup banner: a count that changes by hour (2026-11-10)', () => {
  const shared: QueueSetup = { ...unknownSetup, queue_structure: 'shared_queue', capacity_mode: 'unlimited', abandonment_mode: 'not_modeled', event_period_basis: 'per_date' }
  const sentence = 'Fixed server count, or tick Staffing varies by period if your counters change by hour'

  function renderIncomplete(setup: QueueSetup) {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysisWith(setup).analysis, setup_status: 'incomplete' } })
    vi.mocked(listAnalysisDatasets).mockResolvedValue({ datasets: [{ id: 4, name: 'records', is_current: true, purpose: 'planning', validation: { ok: true } }] } as never)
    vi.mocked(getAnalysisCurrent).mockRejectedValue(new Error('not needed'))
    renderPage()
  }

  afterEach(() => {
    vi.mocked(listAnalysisDatasets).mockReset().mockImplementation(async () => ({ datasets: [] }))
    vi.mocked(getAnalysisCurrent).mockReset()
  })

  it('tells a shared Setup with a current file to set a count or tick Staffing varies', async () => {
    renderIncomplete(shared)
    const banner = await screen.findByTestId('setup-incomplete')
    expect(banner).toHaveTextContent(`NovaQ still needs: ${sentence}.`)
    // The Advanced settings field keeps its own label.
    expect(screen.getByLabelText('Fixed server count')).toHaveAttribute('id', 'server-count')
  })

  it('does not name the count once Staffing varies is ticked', async () => {
    renderIncomplete({ ...shared, staffing_varies_by_period: true, capacity_mode: 'finite' })
    const banner = await screen.findByTestId('setup-incomplete')
    expect(banner).not.toHaveTextContent(sentence)
    expect(banner).not.toHaveTextContent('Fixed server count')
  })

  it('does not name the count once a fixed count is set', async () => {
    renderIncomplete({ ...shared, fixed_server_count: 3, capacity_mode: 'finite' })
    const banner = await screen.findByTestId('setup-incomplete')
    expect(banner).not.toHaveTextContent(sentence)
    expect(banner).not.toHaveTextContent('Fixed server count')
  })
})

describe('workbook confirmation focus (2026-11-10)', () => {
  const differentSaved = { ...unknownSetup, queue_structure: 'separate_queues' as const, queue_ids: ['lane_a'] }

  async function openConfirmation() {
    getAnalysisMock.mockResolvedValue(analysisWith(differentSaved))
    previewMock.mockResolvedValue(preview({ needs_confirmation: true }))
    const opened = await uploadFile('novamart.xlsx')
    const title = await screen.findByText('This file would change your saved Setup')
    return { ...opened, title }
  }

  it('moves focus to the title, never to Replace, and announces the box', async () => {
    const { user, title } = await openConfirmation()
    await waitFor(() => expect(document.activeElement).toBe(title))
    expect(title.closest('.alert')).toHaveAttribute('role', 'status')
    const replace = screen.getByRole('button', { name: 'Replace Setup and upload' })
    expect(document.activeElement).not.toBe(replace)
    await user.tab()
    expect(document.activeElement).toBe(replace)
  })

  it('returns focus to Upload and process on Cancel and uploads nothing', async () => {
    const { user, title } = await openConfirmation()
    await waitFor(() => expect(document.activeElement).toBe(title))
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByRole('button', { name: 'Upload and process' })))
    expect(uploadMock).not.toHaveBeenCalled()
  })

  it('moves focus to the success message after Replace', async () => {
    const { user, file } = await openConfirmation()
    await user.click(screen.getByRole('button', { name: 'Replace Setup and upload' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledWith(7, file, { applySetup: true }))
    const message = await screen.findByText('Input data is valid.')
    await waitFor(() => expect(document.activeElement).toBe(message))
    expect(message).toHaveAttribute('role', 'status')
  })

  it('moves focus to the error message when the upload after Replace fails', async () => {
    uploadMock.mockRejectedValue(Object.assign(new Error('422'), { response: { status: 422, data: { detail: 'The file could not be read.' } } }))
    const { user } = await openConfirmation()
    await user.click(screen.getByRole('button', { name: 'Replace Setup and upload' }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('The file could not be read.')
    await waitFor(() => expect(document.activeElement).toBe(alert))
  })

  it('leaves focus on the file input when the file changes while the box is open', async () => {
    const { title } = await openConfirmation()
    await waitFor(() => expect(document.activeElement).toBe(title))
    const input = screen.getByLabelText('Upload Data')
    // A browser returns focus to the input when the file picker closes, before `change` fires.
    // user.upload focuses it again after `change`, which would hide a wrong focus move.
    input.focus()
    fireEvent.change(input, { target: { files: [new File(['y'], 'other.xlsx')] } })
    expect(screen.queryByText('This file would change your saved Setup')).not.toBeInTheDocument()
    // Let React run the file change's effects before reading focus.
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 0)) })
    expect(document.activeElement).not.toBe(screen.getByRole('button', { name: 'Upload and process' }))
    expect(document.activeElement).toBe(input)
    expect(uploadMock).not.toHaveBeenCalled()
  })
})
