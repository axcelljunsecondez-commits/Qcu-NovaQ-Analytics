import { beforeEach, describe, expect, it, vi } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import type { QueueSetup } from '../api/types'
import { AnalysisSetupPage } from './AnalysisSetupPage'
import { GuidedSetupPage } from './GuidedSetupPage'

const getAnalysisMock = vi.fn()
const patchAnalysisMock = vi.fn()
const listAnalysisDatasetsMock = vi.fn()
const getAnalysisCurrentMock = vi.fn()

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: (...args: unknown[]) => patchAnalysisMock(...args),
  listAnalysisDatasets: (...args: unknown[]) => listAnalysisDatasetsMock(...args),
  getAnalysisCurrent: (...args: unknown[]) => getAnalysisCurrentMock(...args),
  uploadAnalysisDataset: vi.fn(),
}))

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

const unknownSetup = {
  queue_structure: 'unknown',
  fixed_server_count: null,
  staffing_varies_by_period: false,
  capacity_mode: 'unknown',
  total_system_capacity: null,
  abandonment_mode: 'unknown',
  patience_rate_per_hour: null,
  segments: [],
  separate_queue_closure_policy: 'drain_existing',
  queue_ids: [],
  breaks: [],
}

const analysis = {
  id: 7,
  name: 'Unanswered setup',
  service_type: null,
  location_label: null,
  queue_setup: unknownSetup,
  setup_status: 'incomplete',
  archived_at: null,
  created_at: '2026-09-13T00:00:00Z',
  updated_at: '2026-09-13T00:00:00Z',
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue({ analysis })
  patchAnalysisMock.mockReset().mockResolvedValue({ analysis })
  listAnalysisDatasetsMock.mockReset().mockResolvedValue({ datasets: [] })
  getAnalysisCurrentMock.mockReset()
})

describe('setup semantic contracts', () => {
  it('submits untouched canonical setup as unknown and null rather than analytical defaults', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} />
      </Routes>,
      { route: '/analyses/7/setup' },
    )

    expect(await screen.findByLabelText('Queue structure')).toHaveValue('unknown')
    expect(screen.getByLabelText('Capacity mode')).toHaveValue('unknown')
    expect(screen.getByLabelText('Abandonment')).toHaveValue('unknown')
    expect(screen.getByLabelText('Fixed server count')).toHaveValue(null)

    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: unknownSetup,
    }))
  })

  it('renders the Guided Setup chooser without persisting until confirmation', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/guided-setup" element={<GuidedSetupPage />} />
        <Route path="/analyses/:analysisId/setup" element={<div>Canonical setup</div>} />
      </Routes>,
      { route: '/analyses/7/guided-setup' },
    )

    expect(await screen.findByText('Help me choose')).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
    // Answering "No" then "Yes" recommends Separate Queues and requires confirmation.
    await user.click(screen.getAllByRole('radio', { name: 'No' })[0])
    await user.click((await screen.findAllByRole('radio', { name: 'Yes' }))[1])
    expect(await screen.findByText('Recommended structure:')).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText('Queue ID 1'), 'north')
    await user.click(screen.getByRole('button', { name: 'Add queue' }))
    await user.type(screen.getByLabelText('Queue ID 2'), 'south')
    await user.click(screen.getByRole('button', { name: /Use Separate Queues/ }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: expect.objectContaining({ queue_structure: 'separate_queues', queue_ids: ['north', 'south'] }),
    }))
    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
  })

  it('keeps unknown answers unknown and recommends Shared Queue on Yes', async () => {
    const user = userEvent.setup()
    renderWithProviders(
      <Routes>
        <Route path="/analyses/:analysisId/guided-setup" element={<GuidedSetupPage />} />
        <Route path="/analyses/:analysisId/setup" element={<div>Canonical setup</div>} />
      </Routes>,
      { route: '/analyses/7/guided-setup' },
    )
    expect(await screen.findByText(/stay unknown/)).toBeInTheDocument()
    expect(screen.queryByText('Recommended structure:')).not.toBeInTheDocument()
    await user.click(screen.getByRole('radio', { name: 'Yes' }))
    expect(await screen.findByText('Recommended structure:')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: /Use Shared Queue/ }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: expect.objectContaining({ queue_structure: 'shared_queue' }),
    }))
  })

  it('rejects a zero patience rate locally when abandonment modeling is selected', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, abandonment_mode: 'modeled', patience_rate_per_hour: 0 } } })
    const user = userEvent.setup()
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    expect(await screen.findByLabelText('Patience rate per hour (theta)')).toHaveValue(0)
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Patience rate must be greater than zero')
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('configures arbitrary queue names through the dynamic editor', async () => {
    const user = userEvent.setup()
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    await user.selectOptions(await screen.findByLabelText('Queue structure'), 'separate_queues')
    expect(screen.getByText('Configured physical queues')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Add queue' }))
    await user.type(screen.getByLabelText('Queue ID 1'), 'north')
    await user.click(screen.getByRole('button', { name: 'Add queue' }))
    await user.type(screen.getByLabelText('Queue ID 2'), 'south')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: expect.objectContaining({ queue_ids: ['north', 'south'] }),
    }))
  })

  it('reloads persisted arbitrary queue IDs into the editor', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['cashier_a', 'Lane-A'] } } })
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    expect(await screen.findByDisplayValue('cashier_a')).toBeInTheDocument()
    expect(screen.getByDisplayValue('Lane-A')).toBeInTheDocument()
  })

  it('rejects blank and duplicate queue IDs before saving', async () => {
    const user = userEvent.setup()
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['north'] } } })
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    await screen.findByDisplayValue('north')
    await user.click(screen.getByRole('button', { name: 'Add queue' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('non-empty')
    expect(patchAnalysisMock).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText('Queue ID 2'), 'north')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('unique')
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('shows active service-line controls only for variable separate staffing', async () => {
    const user = userEvent.setup()
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['queue_1', 'queue_2'], staffing_varies_by_period: false } } })
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    expect(await screen.findByDisplayValue('queue_1')).toBeInTheDocument()
    expect(screen.getByDisplayValue('queue_2')).toBeInTheDocument()
    expect(screen.getByText('Add time segment')).toBeInTheDocument()
    expect(screen.queryByRole('checkbox', { name: 'queue_1' })).not.toBeInTheDocument()
    await user.click(screen.getByLabelText('Staffing varies by period'))
    expect(screen.getByText('Add time segment')).toBeInTheDocument()
  })

  it('blocks removing a queue set while a removed line is selected in a segment', async () => {
    const user = userEvent.setup()
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['queue_1', 'queue_2'], staffing_varies_by_period: true, segments: [{ id: 'segment_1', start_time: '07:00:00', end_time: '08:00:00', active_queue_ids: ['queue_1', 'queue_2'] }] } } })
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    await screen.findByDisplayValue('queue_2')
    await user.click(screen.getByRole('button', { name: 'Remove queue_2' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Remove that queue from time segment activity')
    expect(screen.getByDisplayValue('queue_2')).toBeInTheDocument()
  })

  it('serializes active lines and preserves mixed segment edits on save and reload', async () => {
    const user = userEvent.setup()
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['queue_1', 'queue_2'], staffing_varies_by_period: true, segments: [] } } })
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    await screen.findByText('Configured physical queues')
    await user.click(screen.getByText('Add time segment'))
    const start = screen.getByLabelText('Start time')
    const end = screen.getByLabelText('End time')
    await user.clear(start)
    await user.type(start, '07:00')
    await user.clear(end)
    await user.type(end, '07:15')
    await user.click(screen.getByRole('checkbox', { name: 'queue_2' }))
    await user.click(screen.getByRole('button', { name: 'Add time segment' }))
    expect(screen.getAllByLabelText('Start time')).toHaveLength(2)
    const starts = screen.getAllByLabelText('Start time')
    const ends = screen.getAllByLabelText('End time')
    await user.clear(starts[1])
    await user.type(starts[1], '07:15')
    await user.clear(ends[1])
    await user.type(ends[1], '07:30')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: expect.objectContaining({
        queue_ids: ['queue_1', 'queue_2'],
        segments: expect.arrayContaining([expect.objectContaining({ start_time: '07:00', end_time: '07:15', active_queue_ids: ['queue_1'] })]),
      }),
    }))
    expect(screen.getAllByRole('button', { name: 'Remove time segment' })).toHaveLength(2)
  })

  it('locks queue structure read-only for established analyses without leaking semantics', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'separate_queues', queue_ids: ['queue_1', 'queue_2'] } } })
    const { unmount } = renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    expect(await screen.findByTestId('queue-structure-readonly')).toHaveTextContent('Separate queues')
    expect(screen.queryByRole('combobox', { name: 'Queue structure' })).not.toBeInTheDocument()
    expect(screen.getByText('Configured physical queues')).toBeInTheDocument()
    unmount()
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: { ...unknownSetup, queue_structure: 'shared_queue', fixed_server_count: 5 } } })
    renderWithProviders(<Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>, { route: '/analyses/7/setup' })
    expect(await screen.findByTestId('queue-structure-readonly')).toHaveTextContent('One shared queue')
    expect(screen.queryByText('Configured physical queues')).not.toBeInTheDocument()
  })
})

describe('separate server break schedule', () => {
  const separateSetup: QueueSetup = {
    queue_structure: 'separate_queues',
    fixed_server_count: 1,
    staffing_varies_by_period: false,
    capacity_mode: 'unlimited',
    total_system_capacity: null,
    abandonment_mode: 'not_modeled',
    patience_rate_per_hour: null,
    segments: [],
    separate_queue_closure_policy: 'drain_existing',
    queue_ids: ['cashier_3', 'express'],
    breaks: [],
  }

  function renderSeparateSetup(setup = separateSetup) {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: setup } })
    return renderWithProviders(
      <Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>,
      { route: '/analyses/7/setup' },
    )
  }

  it('renders a break editor only for separate queues', async () => {
    renderSeparateSetup()
    expect(await screen.findByText('Server break schedule')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Add break' })).toBeInTheDocument()
  })

  it('shows no break editor for shared queues', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: {
      ...separateSetup, queue_structure: 'shared_queue', queue_ids: [],
    } } })
    renderWithProviders(
      <Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>,
      { route: '/analyses/7/setup' },
    )
    await screen.findByTestId('queue-structure-readonly')
    expect(screen.queryByText('Server break schedule')).not.toBeInTheDocument()
    expect(screen.queryByRole('button', { name: 'Add break' })).not.toBeInTheDocument()
  })

  it('adds a break and saves the explicit schedule', async () => {
    const user = userEvent.setup()
    renderSeparateSetup()
    await screen.findByText('Server break schedule')
    await user.click(screen.getByRole('button', { name: 'Add break' }))
    await user.selectOptions(screen.getByLabelText('Break queue 1'), 'cashier_3')
    await user.type(screen.getByLabelText('Break start 1'), '11:00')
    await user.type(screen.getByLabelText('Break duration 1 (minutes)'), '60')
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: expect.objectContaining({
        breaks: [{ queue_id: 'cashier_3', scheduled_start_time: '11:00', duration_minutes: 60 }],
      }),
    }))
  })

  it('removes a break without touching other breaks', async () => {
    const user = userEvent.setup()
    renderSeparateSetup({
      ...separateSetup,
      breaks: [
        { queue_id: 'cashier_3', scheduled_start_time: '11:00', duration_minutes: 60 },
        { queue_id: 'express', scheduled_start_time: '12:00', duration_minutes: 30 },
      ],
    })
    await screen.findByText('Server break schedule')
    await user.click(screen.getByRole('button', { name: 'Remove break 1' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(7, {
      queue_setup: expect.objectContaining({
        breaks: [{ queue_id: 'express', scheduled_start_time: '12:00', duration_minutes: 30 }],
      }),
    }))
  })

  it('blocks removing a queue that has a configured break', async () => {
    const user = userEvent.setup()
    renderSeparateSetup({
      ...separateSetup,
      breaks: [{ queue_id: 'cashier_3', scheduled_start_time: '11:00', duration_minutes: 60 }],
    })
    await screen.findByText('Server break schedule')
    await user.click(screen.getByRole('button', { name: 'Remove cashier_3' }))
    expect(await screen.findByText(/configured breaks/)).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('reloads persisted breaks into the editor verbatim', async () => {
    getAnalysisMock.mockResolvedValue({ analysis: { ...analysis, queue_setup: {
      ...separateSetup,
      breaks: [{ queue_id: 'express', scheduled_start_time: '09:05', duration_minutes: 15 }],
    } } })
    renderWithProviders(
      <Routes><Route path="/analyses/:analysisId/setup" element={<AnalysisSetupPage />} /></Routes>,
      { route: '/analyses/7/setup' },
    )
    expect(await screen.findByDisplayValue('09:05')).toBeInTheDocument()
    expect(screen.getByDisplayValue('15')).toBeInTheDocument()
  })
})
