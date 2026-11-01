import { describe, expect, it, vi, beforeEach } from 'vitest'
import { Route, Routes } from 'react-router-dom'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../test/test-utils'
import { NewAnalysisPage } from './NewAnalysisPage'
import { recommend } from '../lib/structureRecommendation'

const createAnalysisMock = vi.fn()

vi.mock('../api/analyses', () => ({
  createAnalysis: (...args: unknown[]) => createAnalysisMock(...args),
}))

function renderPage(route = '/analyses/new') {
  return renderWithProviders(
    <Routes>
      <Route path="/analyses/new" element={<NewAnalysisPage />} />
      <Route path="/analyses/:analysisId/data" element={<div>Canonical setup</div>} />
      <Route path="/analyses/:analysisId/guided-setup" element={<div>Guided chooser</div>} />
      <Route path="/results" element={<div>Results destination</div>} />
      <Route path="/simulation/replay" element={<div>Replay destination</div>} />
    </Routes>,
    { route },
  )
}

beforeEach(() => {
  createAnalysisMock.mockReset().mockResolvedValue({
    analysis: { id: 11, queue_setup: { queue_structure: 'shared_queue' } },
  })
})

describe('NewAnalysisPage structure selection', () => {
  it.each([['results', 'Results destination'], ['simulation/replay', 'Replay destination']])('returns a newly created analysis to %s', async (destination, expected) => {
    const user = userEvent.setup()
    renderPage(`/analyses/new?continue=${encodeURIComponent(destination)}`)
    await user.type(await screen.findByLabelText('Analysis Name'), 'new test workspace')
    await user.click(screen.getByRole('button', { name: 'Create analysis' }))
    expect(await screen.findByText(expected)).toBeInTheDocument()
    expect(createAnalysisMock).toHaveBeenCalledTimes(1)
  })

  it.each(['https://example.com', '//example.com', 'login', 'results?analysis=99'])('rejects the unsupported continuation %s', async (destination) => {
    const user = userEvent.setup()
    renderPage(`/analyses/new?continue=${encodeURIComponent(destination)}`)
    await user.type(await screen.findByLabelText('Analysis Name'), 'new test workspace')
    await user.click(screen.getByRole('button', { name: 'Continue to queue setup' }))
    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
  })
  it('offers exactly two primary structures plus help, no model jargon', async () => {
    renderPage()
    expect(await screen.findByRole('radio', { name: /Single Line-Queue for Multiple Counters/ })).toBeChecked()
    expect(screen.getAllByRole('radio', { name: /Line-Queue/ })).toHaveLength(2)
    expect(screen.getByRole('radio', { name: /Separate Line-Queue per Counter/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /one shared line/ })).toBeInTheDocument()
    expect(screen.getByRole('img', { name: /three separate lines/ })).toBeInTheDocument()
    expect(screen.getByText('Not sure which one? Answer two questions')).toBeInTheDocument()
    expect(screen.queryByText(/Single server/i)).not.toBeInTheDocument()
    expect(screen.queryByText(/M\/M\/1|M\/M\/c|M\/G\/c|Parallel M\/G\/1/)).not.toBeInTheDocument()
  })

  it('creates a shared analysis with persisted structure', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(await screen.findByLabelText('Analysis Name'), 'shared shop')
    await user.click(screen.getByRole('button', { name: 'Continue to queue setup' }))
    await waitFor(() => expect(createAnalysisMock).toHaveBeenCalled())
    expect(createAnalysisMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({ queue_setup: expect.objectContaining({ queue_structure: 'shared_queue' }) }),
    )
    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
  })

  it('requires named queues for separate and persists queue ids', async () => {
    const user = userEvent.setup()
    renderPage()
    await user.type(await screen.findByLabelText('Analysis Name'), 'separate shop')
    await user.click(screen.getByRole('radio', { name: /Separate Line-Queue per Counter/ }))
    expect(screen.getByRole('button', { name: 'Continue to queue setup' })).toBeDisabled()
    await user.type(screen.getByLabelText('Queue ID 1'), 'cashier_a')
    await user.click(screen.getByRole('button', { name: 'Add queue' }))
    await user.type(screen.getByLabelText('Queue ID 2'), 'cashier_b')
    await user.click(screen.getByRole('button', { name: 'Continue to queue setup' }))
    await waitFor(() => expect(createAnalysisMock).toHaveBeenCalled())
    expect(createAnalysisMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({
        queue_setup: expect.objectContaining({
          queue_structure: 'separate_queues',
          queue_ids: ['cashier_a', 'cashier_b'],
        }),
      }),
    )
  })

  it('can still create an analysis with the structure decided later', async () => {
    const user = userEvent.setup()
    createAnalysisMock.mockResolvedValue({
      analysis: { id: 12, queue_setup: { queue_structure: 'unknown' } },
    })
    renderPage()
    await user.type(await screen.findByLabelText('Analysis Name'), 'unsure shop')
    await user.click(screen.getByText('Not sure which one? Answer two questions'))
    await user.click(within(screen.getByRole('group', { name: /one common waiting line/ })).getByRole('radio', { name: "I'm not sure" }))
    await user.click(within(screen.getByRole('group', { name: /its own line/ })).getByRole('radio', { name: "I'm not sure" }))
    await user.click(screen.getByRole('button', { name: 'Create and decide later' }))
    await waitFor(() => expect(createAnalysisMock).toHaveBeenCalled())
    expect(createAnalysisMock.mock.calls[0][0]).toEqual(
      expect.objectContaining({ queue_setup: expect.objectContaining({ queue_structure: 'unknown' }) }),
    )
    expect(await screen.findByText('Canonical setup')).toBeInTheDocument()
  })

  it.each([
    ['yes', null, "Single Line-Queue for Multiple Counters"],
    ['no', 'yes', "Separate Line-Queue per Counter"],
    ['unsure', 'yes', "Separate Line-Queue per Counter"],
    ['no', 'no', null],
    ['no', 'unsure', null],
    ['unsure', 'unsure', null],
  ] as const)('inline helper answers %s / %s the same way as Guided setup', async (q1, q2, expected) => {
    expect(recommend(q1, q2)).toBe(expected === null ? null : expected.startsWith('Single') ? 'shared_queue' : 'separate_queues')
    const user = userEvent.setup()
    renderPage()
    await user.click(await screen.findByText('Not sure which one? Answer two questions'))
    const label = { yes: 'Yes', no: 'No', unsure: "I'm not sure" }
    await user.click(within(screen.getByRole('group', { name: /one common waiting line/ })).getByRole('radio', { name: label[q1] }))
    if (q2) await user.click(within(screen.getByRole('group', { name: /its own line/ })).getByRole('radio', { name: label[q2] }))
    if (expected) {
      expect(screen.getByRole('status')).toHaveTextContent(`Recommended structure: ${expected}`)
      await user.click(screen.getByRole('button', { name: 'Use this' }))
      expect(screen.getByRole('radio', { name: new RegExp(expected) })).toBeChecked()
    } else {
      expect(screen.getByRole('status')).toHaveTextContent('do not point to one structure')
      expect(screen.queryByRole('button', { name: 'Use this' })).not.toBeInTheDocument()
    }
    expect(createAnalysisMock).not.toHaveBeenCalled()
  })
})
