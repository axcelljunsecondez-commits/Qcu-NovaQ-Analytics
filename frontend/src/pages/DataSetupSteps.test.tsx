import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { makeQueryClient, renderWithProviders } from '../test/test-utils'
import type { QueueSetup } from '../api/types'
import { AnalysisSetupPage } from './AnalysisSetupPage'

const getAnalysisMock = vi.fn()
const patchMock = vi.fn()
const uploadMock = vi.fn()
const previewMock = vi.fn()

vi.mock('../api/analyses', () => ({
  previewSharedAggregateDataset: vi.fn(async () => ({ mode: 'declined', reasons: [] })),
  applySharedAggregateDataset: vi.fn(),
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: (...args: unknown[]) => patchMock(...args),
  listAnalysisDatasets: vi.fn(async () => ({ datasets: [] })),
  getAnalysisCurrent: vi.fn(),
  uploadAnalysisDataset: (...args: unknown[]) => uploadMock(...args),
  previewAnalysisDataset: (...args: unknown[]) => previewMock(...args),
  downloadSetupWorkbook: vi.fn(),
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

const base: QueueSetup = {
  queue_structure: 'unknown', fixed_server_count: null, staffing_varies_by_period: false, capacity_mode: 'unknown',
  total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null, segments: [],
  separate_queue_closure_policy: 'drain_existing', queue_ids: [], breaks: [],
}
const shared: QueueSetup = { ...base, queue_structure: 'shared_queue' }
const separate: QueueSetup = { ...base, queue_structure: 'separate_queues', queue_ids: ['A', 'B'] }

function analysisWith(setup: QueueSetup) {
  return { analysis: { id: 7, name: 'NovaMart', service_type: null, location_label: null, queue_setup: setup,
    setup_status: 'ready', archived_at: null, created_at: '2026-10-01T00:00:00Z', updated_at: '2026-10-01T00:00:00Z' } }
}

function renderPage(queryClient = makeQueryClient()) {
  return renderWithProviders(
    <Routes><Route path="/analyses/:analysisId/data" element={<AnalysisSetupPage />} /></Routes>,
    { route: '/analyses/7/data', queryClient },
  )
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue(analysisWith(shared))
  patchMock.mockReset().mockResolvedValue({ analysis: { id: 7 } })
  uploadMock.mockReset().mockResolvedValue({ dataset: { id: 9, validation: { ok: true, message: 'Input data is valid.' } } })
  previewMock.mockReset()
})

describe('Data and setup steps (spec §7.6)', () => {
  it('puts the shared-file upload first and keeps templates and Advanced settings optional', async () => {
    const { container } = renderPage()
    expect(await screen.findByRole('heading', { level: 1, name: "Data and Setup" })).toBeInTheDocument()
    const titles = Array.from(container.querySelectorAll('.setup-step-title')).map((node) => node.textContent)
    expect(titles).toEqual(['Add your data'])
    expect(container.querySelector('.setup-optional details.setup-manual')).not.toHaveAttribute('open')
    expect(container.querySelector('details.setup-advanced')).not.toHaveAttribute('open')
    expect(screen.getByRole('group', { name: 'This file is for:' })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Use for planning/ })).not.toBeChecked()
    expect(screen.getByRole('radio', { name: /Review only/ })).not.toBeChecked()
    expect(screen.queryByText('Nothing to review yet. Add your data first.')).not.toBeInTheDocument()
  })

  it('opens Advanced settings while the structure is unknown, and asks for it before the template', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith(base))
    const { container } = renderPage()
    expect(await screen.findByText('Choose how customers line up first; the template depends on it.')).toBeInTheDocument()
    expect(container.querySelector('details.setup-advanced')).toHaveAttribute('open')
  })

  it('adds a fifth step to download the current setup for separate lines', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith(separate))
    const { container } = renderPage()
    expect(await screen.findByRole('heading', { name: 'Download my current setup' })).toBeInTheDocument()
    expect(container.querySelectorAll('.setup-step')).toHaveLength(5)
  })
})

describe('Enter numbers without a file (B9)', () => {
  async function fillTwoHours() {
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: /Use for planning/ }))
    await user.click(await screen.findByText('No file? Enter the numbers yourself'))
    await user.clear(screen.getByLabelText('Number of hours'))
    await user.type(screen.getByLabelText('Number of hours'), '2')
    await user.click(screen.getByRole('button', { name: 'Make rows' }))
    const values: Array<[string, string]> = [
      ['Customers arriving per hour, 08:00–09:00', '40'],
      ['Customers one counter serves per hour, 08:00–09:00', '15'],
      ['Counters open, 08:00–09:00', '3'],
      ['Customers arriving per hour, 09:00–10:00', '55'],
      ['Customers one counter serves per hour, 09:00–10:00', '15'],
    ]
    for (const [label, value] of values) {
      await user.type(screen.getByLabelText(label), value)
    }
    return user
  }

  it('reads the typed planning CSV before an explicit legacy fallback upload, with its cache resets', async () => {
    const queryClient = makeQueryClient()
    queryClient.setQueryData(['workflow', 7], { stale: true })
    renderPage(queryClient)
    const user = await fillTwoHours()
    await user.type(screen.getByLabelText('Counters open, 09:00–10:00'), '4')
    expect(screen.getByText('Saved as "entered-by-you" in your uploaded files.')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Upload these numbers' }))
    await user.click(await screen.findByRole('button', { name: 'Upload and process' }))
    await waitFor(() => expect(uploadMock).toHaveBeenCalledTimes(1))
    const [analysisId, file, options] = uploadMock.mock.calls[0]
    expect(analysisId).toBe(7)
    expect(options).toBeUndefined()
    expect(file.name).toBe('entered-by-you.csv')
    expect(await file.text()).toBe('time,lambda,mu,c\n08:00-09:00,40,15,3\n09:00-10:00,55,15,4\n')
    expect(previewMock).not.toHaveBeenCalled()
    expect(await screen.findByRole('status')).toHaveTextContent('Input data is valid.')
    expect(queryClient.getQueryData(['workflow', 7])).toBeUndefined()
  })

  it('does not upload while a row is incomplete', async () => {
    renderPage()
    const user = await fillTwoHours()
    await user.click(screen.getByRole('button', { name: 'Upload these numbers' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Row 2: counters open must be a whole number from 1 to 100000.')
    expect(uploadMock).not.toHaveBeenCalled()
  })

  it('refuses hours that would run past midnight', async () => {
    renderPage()
    const user = userEvent.setup()
    await user.click(await screen.findByText('No file? Enter the numbers yourself'))
    await user.clear(screen.getByLabelText('First hour starts at'))
    await user.type(screen.getByLabelText('First hour starts at'), '22:00')
    await user.clear(screen.getByLabelText('Number of hours'))
    await user.type(screen.getByLabelText('Number of hours'), '3')
    await user.click(screen.getByRole('button', { name: 'Make rows' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Periods must start and end on the same day.')
    expect(screen.queryByRole('table')).not.toBeInTheDocument()
  })

  it('is offered only for a saved shared line', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith(separate))
    renderPage()
    await screen.findByRole('heading', { name: 'Download my current setup' })
    expect(screen.queryByText('No file? Enter the numbers yourself')).not.toBeInTheDocument()
  })
})

describe('Make periods (separate lines)', () => {
  it('writes back-to-back segments that Save sends unchanged', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith(separate))
    const user = userEvent.setup()
    renderPage()
    const helper = await screen.findByRole('group', { name: 'Make periods' })
    await user.clear(within(helper).getByLabelText('First period starts at'))
    await user.type(within(helper).getByLabelText('First period starts at'), '09:00')
    await user.clear(within(helper).getByLabelText('Number of periods'))
    await user.type(within(helper).getByLabelText('Number of periods'), '3')
    await user.selectOptions(within(helper).getByLabelText('Length of each period'), '30')
    await user.click(within(helper).getByRole('button', { name: 'Make periods' }))
    expect(within(helper).getByRole('button', { name: 'Replace periods' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchMock).toHaveBeenCalledTimes(1))
    expect(patchMock.mock.calls[0][1].queue_setup.segments).toEqual([
      { id: 'segment_1', start_time: '09:00', end_time: '09:30', active_queue_ids: null },
      { id: 'segment_2', start_time: '09:30', end_time: '10:00', active_queue_ids: null },
      { id: 'segment_3', start_time: '10:00', end_time: '10:30', active_queue_ids: null },
    ])
  })

  it('refuses periods that would run past midnight and changes nothing', async () => {
    getAnalysisMock.mockResolvedValue(analysisWith(separate))
    const user = userEvent.setup()
    renderPage()
    const helper = await screen.findByRole('group', { name: 'Make periods' })
    await user.clear(within(helper).getByLabelText('First period starts at'))
    await user.type(within(helper).getByLabelText('First period starts at'), '23:00')
    await user.clear(within(helper).getByLabelText('Number of periods'))
    await user.type(within(helper).getByLabelText('Number of periods'), '1')
    await user.click(within(helper).getByRole('button', { name: 'Make periods' }))
    expect(within(helper).getByRole('alert')).toHaveTextContent('Periods must start and end on the same day.')
    expect(screen.queryByLabelText('Start time')).not.toBeInTheDocument()
  })
})
