import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { NewAnalysisPage } from './NewAnalysisPage'

const createAnalysisMock = vi.fn()

vi.mock('../api/analyses', () => ({
  createAnalysis: (...args: unknown[]) => createAnalysisMock(...args),
}))

function renderPage() {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/new" element={<NewAnalysisPage />} />
      <Route path="/analyses/:analysisId/setup" element={<div>Canonical setup</div>} />
      <Route path="/analyses/:analysisId/guided-setup" element={<div>Guided chooser</div>} />
    </Routes>,
    { route: '/analyses/new' },
  )
}

beforeEach(() => {
  createAnalysisMock.mockReset().mockResolvedValue({
    analysis: { id: 11, queue_setup: { queue_structure: 'shared_queue' } },
  })
})

describe('NewAnalysisPage structure selection', () => {
  it('offers exactly two primary structures plus help, no model jargon', async () => {
    renderPage()
    expect(await screen.findByRole('dialog')).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Shared Queue/ })).toBeInTheDocument()
    expect(screen.getByRole('radio', { name: /Separate Queues/ })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /Help me choose/ })).toBeInTheDocument()
    expect(screen.queryByText(/Single server/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/M\/M\/1|M\/M\/c|M\/G\/c|Parallel M\/G\/1/)).not.toBeInTheDocument()
  })

  it('creates a shared analysis with persisted structure', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(await screen.findByLabelText('Analysis name'), 'shared shop')
    await user.click(screen.getByRole('button', { name: 'Continue to queue setup' }))
    await waitFor(() => expect(createAnalysisMock).toHaveBeenCalled())
    expect(createAnalysisMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({ queue_setup: expect.objectContaining({ queue_structure: 'shared_queue' }) }),
    )
    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
  })

  it('requires a queue count for separate and persists queue ids', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(await screen.findByLabelText('Analysis name'), 'separate shop')
    await user.click(screen.getByRole('radio', { name: /Separate Queues/ }))
    expect(screen.getByRole('button', { name: 'Continue to queue setup' })).toBeDisabled()
    await user.type(screen.getByLabelText('Number of separate service lines'), '3')
    await user.click(screen.getByRole('button', { name: 'Continue to queue setup' }))
    await waitFor(() => expect(createAnalysisMock).toHaveBeenCalled())
    expect(createAnalysisMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        queue_setup: expect.objectContaining({
          queue_structure: 'separate_queues',
          queue_ids: ['queue_1', 'queue_2', 'queue_3'],
        }),
      }),
    )
  })

  it('help path creates an unknown-structure analysis bound for guided setup', async () => {
    const user = userEvent.setup()
    createAnalysisMock.mockResolvedValue({
      analysis: { id: 12, queue_setup: { queue_structure: 'unknown' } },
    })
    renderPage()
    await user.type(await screen.findByLabelText('Analysis name'), 'unsure shop')
    await user.click(screen.getByRole('button', { name: /Help me choose/ }))
    await waitFor(() => expect(createAnalysisMock).toHaveBeenCalled())
    expect(createAnalysisMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({ queue_setup: expect.objectContaining({ queue_structure: 'unknown' }) }),
    )
    expect(await screen.findByText('Guided chooser')).toBeInTheDocument()
  })
})
