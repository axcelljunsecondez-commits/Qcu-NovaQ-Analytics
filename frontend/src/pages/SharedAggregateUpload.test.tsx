import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Link, Route, Routes } from 'react-router-dom'
import { act, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeQueryClient, renderWithProviders } from '../test/test-utils'
import type { QueueSetup, SharedAggregatePreviewOut } from '../api/types'
import { AnalysisSetupPage } from './AnalysisSetupPage'

// Synthetic API fixtures: the real owner's CSV is exercised by the isolated integration check.
const mocks = vi.hoisted(() => ({ analysis: vi.fn(), datasets: vi.fn(), current: vi.fn(), patch: vi.fn(),
  upload: vi.fn(), workbook: vi.fn(), preview: vi.fn(), apply: vi.fn(), closing: vi.fn(), saveClosing: vi.fn() }))
vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => mocks.analysis(...args),
  listAnalysisDatasets: (...args: unknown[]) => mocks.datasets(...args),
  getAnalysisCurrent: (...args: unknown[]) => mocks.current(...args),
  patchAnalysis: (...args: unknown[]) => mocks.patch(...args),
  uploadAnalysisDataset: (...args: unknown[]) => mocks.upload(...args),
  previewAnalysisDataset: (...args: unknown[]) => mocks.workbook(...args),
  previewSharedAggregateDataset: (...args: unknown[]) => mocks.preview(...args),
  applySharedAggregateDataset: (...args: unknown[]) => mocks.apply(...args),
  downloadSetupWorkbook: vi.fn(),
}))
vi.mock('../api/continuous', () => ({ getClosingPolicy: (...args: unknown[]) => mocks.closing(...args), putClosingPolicy: (...args: unknown[]) => mocks.saveClosing(...args) }))
vi.mock('../api/templates', () => ({ getTemplateGuide: vi.fn(), downloadTemplate: vi.fn() }))
vi.mock('../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))

const saved: QueueSetup = { queue_structure: 'shared_queue', fixed_server_count: null, staffing_varies_by_period: false,
  capacity_mode: 'unknown', total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null,
  segments: [], separate_queue_closure_policy: 'drain_existing', queue_ids: [], breaks: [] }
const derived: QueueSetup = { ...saved, staffing_varies_by_period: true, segments: [
  { id: '08:00-09:00', start_time: '08:00', end_time: '09:00', active_queue_ids: null },
  { id: '09:00-10:00', start_time: '09:00', end_time: '10:00', active_queue_ids: null },
] }
const preview: SharedAggregatePreviewOut = {
  mode: 'shared_aggregate', file_digest: 'file-digest', setup_revision: 'setup-revision', saved_setup: saved,
  derived_setup: derived, needs_confirmation: false, diff: [], unresolved: ['capacity_mode', 'abandonment_mode'], conflicts: [], reasons: [],
  facts: { filename: 'rates.csv', row_count: 2, start_time: '08:00', end_time: '10:00', counter_min: 1, counter_max: 2,
    lambda_min: 4, lambda_max: 5, mu_min: 6, mu_max: 6,
    rows: [{ time: '08:00-09:00', lambda: 4, mu: 6, c: 1 }, { time: '09:00-10:00', lambda: 5, mu: 6, c: 2 }] },
}
const project = { id: 7, name: 'Test shared line', queue_setup: saved, setup_status: 'incomplete', archived_at: null }
const dataset = { id: 19, analysis_id: 7, name: 'rates', source_filename: 'rates.csv', row_count: 2,
  validation: { ok: true, message: 'Input data is valid.', schema: 'aggregate' }, purpose: 'planning', is_current: true }
const applyResult = { dataset, analysis: { ...project, queue_setup: { ...derived, capacity_mode: 'unlimited', abandonment_mode: 'not_modeled' }, setup_status: 'ready_for_aggregate' }, duplicate: false }
const file = (name = 'rates.csv') => new File(['time,lambda,mu,c\n08:00-09:00,4,6,1\n09:00-10:00,5,6,2'], name, { type: 'text/csv' })

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => { resolve = done })
  return { promise, resolve }
}

function renderPage(lang: 'en' | 'tl' = 'en') {
  return renderWithProviders(<Routes><Route path="/analyses/:analysisId/data" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/data', lang })
}
async function chooseFile() {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('radio', { name: /Use for planning/ }))
  const selected = file()
  await user.upload(screen.getByLabelText('Upload Data'), selected)
  return { user, selected }
}
async function answerSupported(user: ReturnType<typeof userEvent.setup>) {
  await user.click(await screen.findByRole('radio', { name: 'No known limit' }))
  await user.click(screen.getByRole('radio', { name: 'No, customers wait' }))
}

beforeEach(() => {
  Object.values(mocks).forEach((mock) => mock.mockReset())
  mocks.analysis.mockResolvedValue({ analysis: project })
  mocks.datasets.mockResolvedValue({ datasets: [] })
  mocks.current.mockResolvedValue({ dataset, selected_model: 'M/M/c', explanations: [] })
  mocks.preview.mockResolvedValue(preview)
  mocks.apply.mockResolvedValue(applyResult)
  mocks.closing.mockResolvedValue({ closing_policy: null })
  mocks.saveClosing.mockResolvedValue({ closing_policy: 'DRAIN' })
  mocks.workbook.mockResolvedValue({ mode: 'legacy' })
  mocks.upload.mockResolvedValue({ dataset })
})

describe('shared planning file read and apply', () => {
  it('automatically previews a planning file without writing or asking for the fixed count', async () => {
    renderPage()
    const { selected } = await chooseFile()
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledWith(7, selected))
    const summary = await screen.findByRole('region', { name: "Here's what NovaQ read from your file" })
    expect(summary).toHaveTextContent('rates.csv · 2 rows')
    expect(summary).toHaveTextContent('08:00–10:00')
    expect(mocks.apply).not.toHaveBeenCalled()
    expect(mocks.upload).not.toHaveBeenCalled()
    expect(screen.queryByTestId('setup-incomplete')).not.toBeInTheDocument()
  })

  it('requires explicit missing answers, applies once, and saves an optional closing rule afterward', async () => {
    renderPage()
    const { user, selected } = await chooseFile()
    await screen.findByRole('radio', { name: 'No known limit' })
    expect(screen.getByRole('button', { name: 'Upload and process' })).toBeDisabled()
    await answerSupported(user)
    await user.click(screen.getByRole('radio', { name: 'Finish serving customers already waiting' }))
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.apply).toHaveBeenCalledWith(7, selected, {
      file_digest: 'file-digest', setup_revision: 'setup-revision', confirm_replace: false,
      choices: { capacity_mode: 'unlimited', total_system_capacity: null, abandonment_mode: 'not_modeled', patience_rate_per_hour: null },
    }))
    await waitFor(() => expect(mocks.saveClosing).toHaveBeenCalledWith(7, 'DRAIN'))
    expect(mocks.apply.mock.invocationCallOrder[0]).toBeLessThan(mocks.saveClosing.mock.invocationCallOrder[0])
    expect(await screen.findByRole('link', { name: 'Full-day run' })).toHaveAttribute('href', '/simulation/results?analysis=7&plan=current')
    expect(screen.getByRole('link', { name: 'View Analysis results' })).toHaveAttribute('href', '/results?analysis=7')
    expect(screen.getByRole('region', { name: "Here's what NovaQ read from your file" })).toBeInTheDocument()
    expect(mocks.apply).toHaveBeenCalledTimes(1)
  })

  it('keeps explicit unknown answers unknown and allows deciding closing later', async () => {
    renderPage()
    const { user } = await chooseFile()
    await user.click(await screen.findByRole('radio', { name: "I'm not sure" }))
    await user.click(screen.getByRole('radio', { name: "I don't know" }))
    await user.click(screen.getByRole('radio', { name: 'Decide later' }))
    expect(screen.getByText('You can save now. The full-day run stays unavailable until you answer.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.apply).toHaveBeenCalled())
    expect(mocks.apply.mock.calls[0][2].choices).toMatchObject({ capacity_mode: 'unknown', abandonment_mode: 'unknown' })
    expect(mocks.saveClosing).not.toHaveBeenCalled()
  })

  it('shows replacement confirmation and cancel writes nothing', async () => {
    mocks.preview.mockResolvedValue({ ...preview, needs_confirmation: true, diff: [{ field: 'fixed_server_count', saved: 5, derived: null }] })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    expect(await screen.findByText('This file would change your saved Setup')).toBeInTheDocument()
    expect(mocks.apply).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(mocks.apply).not.toHaveBeenCalled()
    expect(screen.queryByText('This file would change your saved Setup')).not.toBeInTheDocument()
  })

  it('confirms a planning-file replacement without claiming an unchanged Setup will change', async () => {
    mocks.preview.mockResolvedValue({ ...preview, needs_confirmation: true, diff: [] })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    const cancel = await screen.findByRole('button', { name: 'Cancel' })
    const confirmation = cancel.closest('[role="status"]') as HTMLElement
    expect(within(confirmation).getByRole('button', { name: 'Upload and process' })).toBeEnabled()
    expect(confirmation).toHaveTextContent('Results made from the previous planning file will need to be rerun.')
    expect(screen.queryByText('This file would change your saved Setup')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Replace Setup and upload' })).not.toBeInTheDocument()
    expect(mocks.apply).not.toHaveBeenCalled()
    await user.click(cancel)
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('uses the explicit old upload after a declined read without dropping supplied columns', async () => {
    mocks.preview.mockResolvedValue({ ...preview, mode: 'declined', facts: null, derived_setup: null,
      reasons: [{ code: 'out_of_scope', detail: 'This file includes service-time variance.' }] })
    renderPage()
    const { user, selected } = await chooseFile()
    expect(await screen.findByText("NovaQ can't fill in the Setup from this file. You can still upload it the usual way.")).toBeInTheDocument()
    expect(screen.getByText('This file includes service-time variance.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(7, selected))
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('never reads or applies a review-only file automatically', async () => {
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /Review only/ }))
    const selected = file()
    await user.upload(screen.getByLabelText('Upload Data'), selected)
    expect(mocks.preview).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(7, selected, { purpose: 'review' }))
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('requires the real finite capacity and positive patience rate, without enabling full-day support', async () => {
    renderPage()
    const { user } = await chooseFile()
    await user.click(await screen.findByRole('radio', { name: 'Yes, there is a limit' }))
    await user.click(screen.getByRole('radio', { name: 'Yes, customers leave' }))
    const apply = screen.getByRole('button', { name: 'Upload and process' })
    expect(apply).toBeDisabled()
    await user.type(screen.getByLabelText('Total customers in system (including service)'), '15')
    await user.type(screen.getByLabelText('Patience rate per hour (theta)'), '0')
    expect(apply).toBeDisabled()
    await user.clear(screen.getByLabelText('Patience rate per hour (theta)'))
    await user.type(screen.getByLabelText('Patience rate per hour (theta)'), '0.5')
    expect(apply).toBeEnabled()
    expect(screen.getByText('Waiting-room limits and customers leaving are not in the full-day run yet.')).toBeInTheDocument()
    await user.click(apply)
    await waitFor(() => expect(mocks.apply).toHaveBeenCalled())
    expect(mocks.apply.mock.calls[0][2].choices).toMatchObject({ capacity_mode: 'finite', total_system_capacity: 15, abandonment_mode: 'modeled', patience_rate_per_hour: 0.5 })
  })

  it('preserves known saved choices and asks for none of them again', async () => {
    const known = { ...saved, capacity_mode: 'finite', total_system_capacity: 15, abandonment_mode: 'modeled', patience_rate_per_hour: 0.5 } as QueueSetup
    mocks.preview.mockResolvedValue({ ...preview, saved_setup: known, derived_setup: { ...derived, ...known, segments: derived.segments }, unresolved: [] })
    mocks.closing.mockResolvedValue({ closing_policy: 'HARD_CUTOFF' })
    renderPage()
    const { user } = await chooseFile()
    const apply = await screen.findByRole('button', { name: 'Upload and process' })
    expect(screen.queryByRole('radio', { name: 'No known limit' })).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: 'Finish serving customers already waiting' })).not.toBeInTheDocument()
    await user.click(apply)
    await waitFor(() => expect(mocks.apply).toHaveBeenCalled())
    expect(mocks.apply.mock.calls[0][2].choices).toEqual({})
    expect(mocks.saveClosing).not.toHaveBeenCalled()
  })

  it('ignores a late old-file response and clears answers when the file changes', async () => {
    const old = deferred<SharedAggregatePreviewOut>()
    mocks.preview.mockReturnValueOnce(old.promise).mockResolvedValueOnce({ ...preview, file_digest: 'second', facts: { ...preview.facts!, filename: 'new.csv' } })
    renderPage()
    const { user } = await chooseFile()
    await user.upload(screen.getByLabelText('Upload Data'), file('new.csv'))
    await answerSupported(user)
    await act(async () => { old.resolve(preview); await old.promise })
    expect(screen.getByRole('region', { name: "Here's what NovaQ read from your file" })).toHaveTextContent('new.csv')
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.apply).toHaveBeenCalled())
    expect(mocks.apply.mock.calls[0][2].file_digest).toBe('second')
  })

  it('ignores a planning read that returns after changing to review-only', async () => {
    const pending = deferred<SharedAggregatePreviewOut>()
    mocks.preview.mockReturnValue(pending.promise)
    renderPage()
    const { user } = await chooseFile()
    await user.click(screen.getByRole('radio', { name: /Review only/ }))
    await act(async () => { pending.resolve(preview); await pending.promise })
    expect(screen.queryByRole('region', { name: "Here's what NovaQ read from your file" })).not.toBeInTheDocument()
    expect(screen.queryByRole('radio', { name: 'No known limit' })).not.toBeInTheDocument()
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('resets the file on navigation and ignores the old analysis response', async () => {
    const pending = deferred<SharedAggregatePreviewOut>()
    mocks.preview.mockReturnValue(pending.promise)
    mocks.analysis.mockImplementation(async (id: number) => ({ analysis: { ...project, id, name: `Analysis ${id}` } }))
    renderWithProviders(<><Link to="/analyses/8/data">Other analysis</Link><Routes><Route path="/analyses/:analysisId/data" element={<AnalysisSetupPage />} /></Routes></>, { route: '/analyses/7/data' })
    const { user } = await chooseFile()
    await user.click(screen.getByRole('link', { name: 'Other analysis' }))
    await act(async () => { pending.resolve(preview); await pending.promise })
    await screen.findByRole('radio', { name: /Use for planning/ })
    expect(screen.getByLabelText('Upload Data')).toHaveValue('')
    expect(screen.queryByRole('region', { name: "Here's what NovaQ read from your file" })).not.toBeInTheDocument()
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('reads the same file again after applying and switching purpose away and back', async () => {
    renderPage()
    const { user, selected } = await chooseFile()
    await answerSupported(user)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await screen.findByRole('link', { name: 'Full-day run' })
    await user.click(screen.getByRole('radio', { name: /Review only/ }))
    await user.click(screen.getByRole('radio', { name: /Use for planning/ }))
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledTimes(2))
    expect(mocks.preview).toHaveBeenLastCalledWith(7, selected)
    expect(await screen.findByRole('button', { name: 'Upload and process' })).toBeDisabled()
  })

  it('suppresses double apply clicks while the same request is pending', async () => {
    const pending = deferred<typeof applyResult>()
    mocks.apply.mockReturnValue(pending.promise)
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.dblClick(screen.getByRole('button', { name: 'Upload and process' }))
    expect(mocks.apply).toHaveBeenCalledTimes(1)
    await act(async () => { pending.resolve(applyResult); await pending.promise })
    await screen.findByRole('link', { name: 'Full-day run' })
  })

  it('waits for saved closing-policy evidence and never overwrites it with a hidden draft', async () => {
    const pending = deferred<{ closing_policy: 'HARD_CUTOFF' }>()
    mocks.closing.mockReturnValue(pending.promise)
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    expect(screen.queryByRole('radio', { name: 'Finish serving customers already waiting' })).not.toBeInTheDocument()
    await act(async () => { pending.resolve({ closing_policy: 'HARD_CUTOFF' }); await pending.promise })
    expect(screen.queryByRole('radio', { name: 'Finish serving customers already waiting' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await screen.findByRole('link', { name: 'Full-day run' })
    expect(mocks.saveClosing).not.toHaveBeenCalled()
  })

  it('shows a closing read error while allowing Dataset and Setup to save without a policy write', async () => {
    mocks.closing.mockRejectedValue({ response: { data: { detail: 'Closing policy could not be loaded.' } } })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    expect(await screen.findByRole('alert')).toHaveTextContent('Closing policy could not be loaded.')
    expect(screen.queryByRole('radio', { name: 'Finish serving customers already waiting' })).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await screen.findByRole('link', { name: 'Full-day run' })
    expect(mocks.saveClosing).not.toHaveBeenCalled()
  })

  it('preserves committed Dataset success and retries only a failed closing write', async () => {
    mocks.saveClosing.mockRejectedValueOnce({ response: { data: { detail: 'Closing save refused.' } } }).mockResolvedValueOnce({ closing_policy: 'DRAIN' })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.click(await screen.findByRole('radio', { name: 'Finish serving customers already waiting' }))
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await screen.findByRole('link', { name: 'Full-day run' })
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('Closing save refused.')
    await user.click(within(alert).getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(mocks.saveClosing).toHaveBeenCalledTimes(2))
    expect(mocks.apply).toHaveBeenCalledTimes(1)
    await waitFor(() => expect(screen.queryByText('Closing save refused.')).not.toBeInTheDocument())
  })

  it('clears answers and reads fresh evidence when the saved Setup changes externally', async () => {
    const queryClient = makeQueryClient()
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/data" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/data', queryClient })
    const { user } = await chooseFile()
    await answerSupported(user)
    act(() => queryClient.setQueryData(['analysis', 7], { analysis: { ...project, queue_setup: { ...saved, fixed_server_count: 6 } } }))
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('radio', { name: 'No known limit' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Upload and process' })).toBeDisabled()
  })

  it('blocks a known finite or modeled Setup missing its required number and opens Advanced for repair', async () => {
    const incomplete = { ...saved, capacity_mode: 'finite', abandonment_mode: 'modeled' } as QueueSetup
    mocks.preview.mockResolvedValue({ ...preview, saved_setup: incomplete, derived_setup: { ...derived, ...incomplete, segments: derived.segments }, unresolved: [] })
    renderPage()
    const { user } = await chooseFile()
    expect(await screen.findByRole('button', { name: 'Upload and process' })).toBeDisabled()
    const capacity = screen.getByText('Finite total system capacity', { selector: 'strong' }).closest('p')!
    expect(capacity).toHaveTextContent('Unavailable')
    await user.click(within(capacity).getByRole('button', { name: 'Change' }))
    await waitFor(() => expect(document.activeElement).toBe(screen.getByLabelText('Capacity mode')))
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it.each(['setup_changed', 'file_changed'])('recovers from %s by reading again without retrying the write', async (code) => {
    mocks.apply.mockRejectedValueOnce({ response: { data: { detail: { code } } } })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('radio', { name: 'No known limit' })).not.toBeChecked()
    expect(screen.getByRole('button', { name: 'Upload and process' })).toBeDisabled()
    expect(screen.getByRole('alert')).toHaveTextContent('Upload failed. Please check the file and try again.')
    expect(mocks.apply).toHaveBeenCalledTimes(1)
    expect(mocks.upload).not.toHaveBeenCalled()
  })

  it('uses only one fresh preview when stale-save recovery also refreshes a changed Setup', async () => {
    const changed = { ...saved, fixed_server_count: 6 }
    mocks.analysis.mockResolvedValueOnce({ analysis: project }).mockResolvedValue({ analysis: { ...project, queue_setup: changed } })
    mocks.preview.mockResolvedValueOnce(preview).mockResolvedValue({ ...preview, saved_setup: changed })
    mocks.apply.mockRejectedValueOnce({ response: { data: { detail: { code: 'setup_changed' } } } })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(mocks.preview).toHaveBeenCalledTimes(2))
    expect(await screen.findByRole('radio', { name: 'No known limit' })).not.toBeChecked()
    expect(mocks.apply).toHaveBeenCalledTimes(1)
  })

  it('keeps server conflict details visible and does not apply', async () => {
    mocks.preview.mockResolvedValue({ ...preview, conflicts: [{ code: 'counter_breaks', detail: 'A saved break is outside these hours.', problems: ['17:00: no counters on duty.'] }] })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    expect(screen.getByRole('alert')).toHaveTextContent('A saved break is outside these hours.')
    expect(screen.getByRole('button', { name: 'Upload and process' })).toBeDisabled()
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('shows a break-conflict detail once when the server repeats it in its problem list', async () => {
    const detail = 'Break at 04:15 is outside the operating hours 05:00-18:00.'
    mocks.preview.mockResolvedValue({ ...preview, conflicts: [{ code: 'breaks_outside_hours', detail, problems: [detail] }] })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    expect(screen.getAllByText(detail)).toHaveLength(1)
    expect(screen.getByRole('button', { name: 'Upload and process' })).toBeDisabled()
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('confirms replacement with readable period values and sends explicit replacement intent', async () => {
    mocks.preview.mockResolvedValue({ ...preview, needs_confirmation: true, diff: [
      { field: 'segments', saved: [], derived: derived.segments },
      { field: 'fixed_server_count', saved: 5, derived: null },
      { field: 'staffing_varies_by_period', saved: false, derived: true },
    ] })
    renderPage()
    const { user } = await chooseFile()
    await answerSupported(user)
    await user.click(screen.getByRole('button', { name: 'Upload and process' }))
    const confirmation = screen.getByText('This file would change your saved Setup').closest('div')!
    expect(confirmation).toHaveTextContent('08:00–09:00, 09:00–10:00')
    expect(confirmation).not.toHaveTextContent('active_queue_ids')
    expect(confirmation).not.toHaveTextContent('null')
    await user.click(within(confirmation).getByRole('button', { name: 'Replace Setup and upload' }))
    await waitFor(() => expect(mocks.apply).toHaveBeenCalled())
    expect(mocks.apply.mock.calls[0][2].confirm_replace).toBe(true)
  })

  it('keeps workbook preview and explicit confirmation after the new reader declines it', async () => {
    mocks.preview.mockResolvedValue({ ...preview, mode: 'declined', facts: null, derived_setup: null, reasons: [{ code: 'multi_sheet', detail: 'Use the workbook upload.' }] })
    mocks.workbook.mockResolvedValue({ mode: 'multi_sheet', derived_setup: { ...saved, queue_structure: 'separate_queues', queue_ids: ['A'] },
      staff: [], breaks: [], errors: [], needs_confirmation: true, diff: [{ field: 'queue_ids', saved: [], derived: ['A'] }] })
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /Use for planning/ }))
    const workbook = new File(['synthetic workbook fixture'], 'book.xlsx')
    await user.upload(screen.getByLabelText('Upload Data'), workbook)
    await user.click(await screen.findByRole('button', { name: 'Upload and process' }))
    await screen.findByText('This file would change your saved Setup')
    expect(mocks.workbook).toHaveBeenCalledWith(7, workbook)
    expect(mocks.upload).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Replace Setup and upload' }))
    await waitFor(() => expect(mocks.upload).toHaveBeenCalledWith(7, workbook, { applySetup: true }))
    expect(mocks.apply).not.toHaveBeenCalled()
  })

  it('hides event period basis only when the authoritative current planning file is aggregate', async () => {
    mocks.datasets.mockResolvedValue({ datasets: [dataset] })
    renderPage()
    await screen.findByLabelText('Upload Data')
    expect(screen.queryByLabelText('Customer data periods')).not.toBeInTheDocument()
  })

  it('uses the three approved Filipino messages and keeps unknown answers explicit', async () => {
    renderPage('tl')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /Gamitin sa pagpaplano/ }))
    await user.upload(screen.getByLabelText('Mag-upload ng Data'), file())
    await user.click(await screen.findByRole('radio', { name: 'Hindi ako sigurado' }))
    expect(screen.getByText("Puwede kang mag-save ngayon. Hindi magagamit ang takbo ng buong araw hangga't hindi ka sumasagot.")).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: 'Pagpasyahan mamaya' })).not.toBeChecked()
  })
})
