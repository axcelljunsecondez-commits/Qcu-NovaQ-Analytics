import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { GuidedSetupPage } from './GuidedSetupPage'

const getAnalysisMock = vi.fn()
const patchAnalysisMock = vi.fn()

vi.mock('../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getAnalysisMock(...args),
  patchAnalysis: (...args: unknown[]) => patchAnalysisMock(...args),
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
}

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/:analysisId/guided-setup" element={<GuidedSetupPage />} />
      <Route path="/analyses/:analysisId/setup" element={<div>Canonical setup</div>} />
    </Routes>,
    { route: '/analyses/7/guided-setup' },
  )
}

beforeEach(() => {
  getAnalysisMock.mockReset().mockResolvedValue({ analysis: { id: 7, queue_setup: unknownSetup } })
  patchAnalysisMock.mockReset().mockResolvedValue({ analysis: { id: 7 } })
})

describe('GuidedSetupPage chooser', () => {
  it('reveals one question at a time and keeps unknowns unpersisted', async () => {
    renderPage()
    expect(await screen.findByText(/stay unknown/)).toBeInTheDocument()
    expect(screen.queryByText('Recommended structure:')).not.toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('recommends shared queue immediately on Yes and persists only on confirm', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Help me choose')
    await user.click(screen.getByRole('radio', { name: 'Yes' }))
    expect(await screen.findByText('Recommended structure:')).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
    await user.click(screen.getByRole('button', { name: 'Use Shared Queue' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(
      7,
      { queue_setup: expect.objectContaining({ queue_structure: 'shared_queue' }) },
    ))
    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
  })

  it('reveals the second question on No and confirms separate with a count', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Help me choose')
    await user.click(screen.getByRole('radio', { name: 'No' }))
    await user.click((await screen.findAllByRole('radio', { name: 'Yes' }))[1])
    expect(await screen.findByText('Recommended structure:')).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Use Separate Queues' }))
    expect(patchAnalysisMock).not.toHaveBeenCalled()
    await user.type(screen.getByLabelText('Number of separate service lines'), '2')
    await user.click(screen.getByRole('button', { name: 'Use Separate Queues' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(
      7,
      { queue_setup: expect.objectContaining({ queue_structure: 'separate_queues', queue_ids: ['queue_1', 'queue_2'] }) },
    ))
  })

  it('shows no recommendation for indecisive answers yet allows explicit choice', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Help me choose')
    await user.click(screen.getByRole('radio', { name: 'No' }))
    await user.click((await screen.findAllByRole('radio', { name: 'No' }))[1])
    expect(await screen.findByRole('status')).toHaveTextContent(/Review your answers or observe/)
    await user.click(screen.getByRole('button', { name: 'Use Shared Queue' }))
    await waitFor(() => expect(patchAnalysisMock).toHaveBeenCalledWith(
      7,
      { queue_setup: expect.objectContaining({ queue_structure: 'shared_queue' }) },
    ))
  })

  it('review answers restarts the flow without persisting', async () => {
    const user = userEvent.setup()
    renderPage()
    await screen.findByText('Help me choose')
    await user.click(screen.getByRole('radio', { name: 'Yes' }))
    await screen.findByText('Recommended structure:')
    await user.click(screen.getByRole('button', { name: 'Review Answers' }))
    expect(await screen.findByText('Do customers form one common waiting line and go to the next available cashier?')).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })

  it('refuses to re-decide an already confirmed structure', async () => {
    getAnalysisMock.mockResolvedValue({
      analysis: { id: 7, queue_setup: { ...unknownSetup, queue_structure: 'shared_queue' } },
    })
    renderPage()
    expect(await screen.findByText('Queue structure is already set for this analysis.')).toBeInTheDocument()
    expect(patchAnalysisMock).not.toHaveBeenCalled()
  })
})
