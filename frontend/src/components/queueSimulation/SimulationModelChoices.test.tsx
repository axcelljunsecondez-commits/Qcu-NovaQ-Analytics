import { beforeEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { QueueSetup } from '../../api/types'
import { makeQueryClient, renderWithProviders } from '../../test/test-utils'
import { SimulationModelChoices } from './SimulationModelChoices'

const mocks = vi.hoisted(() => ({ get: vi.fn(), patch: vi.fn() }))
vi.mock('../../api/analyses', () => ({ getAnalysis: (...args: unknown[]) => mocks.get(...args), patchAnalysis: (...args: unknown[]) => mocks.patch(...args) }))
vi.mock('../../api/auth', () => ({ me: vi.fn(async () => ({ user: null })), login: vi.fn(), logout: vi.fn() }))

const setup: QueueSetup = { queue_structure: 'shared_queue', fixed_server_count: 3, staffing_varies_by_period: false,
  capacity_mode: 'unknown', total_system_capacity: null, abandonment_mode: 'unknown', patience_rate_per_hour: null,
  segments: [], breaks: [], queue_ids: [], separate_queue_closure_policy: 'drain_existing' }
const project = (queue_setup = setup, id = 7) => ({ analysis: { id, queue_setup, archived_at: null } })
const saving = vi.fn()
const editor = (id = 7, disabled = false, focusRequest = 0) => <SimulationModelChoices analysisId={id} disabled={disabled} focusRequest={focusRequest} onPendingChange={saving} />
async function supported() {
  const user = userEvent.setup()
  await user.click(await screen.findByRole('radio', { name: 'No known limit' }))
  await user.click(screen.getByRole('radio', { name: 'No, customers wait' }))
  return user
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.get.mockReset().mockResolvedValue(project())
  mocks.patch.mockReset().mockImplementation(async (id: number, payload: { queue_setup: QueueSetup }) => project(payload.queue_setup, id))
})

describe('Simulation model choices', () => {
  it('keeps unknown values explicit and never saves defaults on read', async () => {
    renderWithProviders(editor())
    expect(await screen.findByRole('radio', { name: "I'm not sure" })).toBeChecked()
    expect(screen.getByRole('radio', { name: "I don't know" })).toBeChecked()
    expect(screen.getByText('You can save now. The full-day run stays unavailable until you answer.')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    expect(mocks.patch).not.toHaveBeenCalled()
    const user = userEvent.setup()
    await user.click(screen.getByRole('radio', { name: 'No known limit' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith(7, { queue_setup: { ...setup, capacity_mode: 'unlimited' } }))
  })

  it('validates real finite capacity and positive patience before saving unsupported choices', async () => {
    renderWithProviders(editor())
    const user = userEvent.setup()
    await user.click(await screen.findByRole('radio', { name: 'Yes, there is a limit' }))
    await user.click(screen.getByRole('radio', { name: 'Yes, customers leave' }))
    const save = screen.getByRole('button', { name: 'Save' })
    const capacity = screen.getByLabelText('Total customers in system (including service)')
    const patience = screen.getByLabelText('Patience rate per hour (theta)')
    expect(save).toBeDisabled()
    fireEvent.change(capacity, { target: { value: '1.5' } })
    fireEvent.change(patience, { target: { value: '0' } })
    expect(save).toBeDisabled()
    fireEvent.change(capacity, { target: { value: '100001' } })
    fireEvent.change(patience, { target: { value: '0.5' } })
    expect(save).toBeDisabled()
    fireEvent.change(capacity, { target: { value: '15' } })
    expect(save).toBeEnabled()
    expect(screen.getByText('Waiting-room limits and customers leaving are not in the full-day run yet.')).toBeInTheDocument()
    await user.click(save)
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith(7, { queue_setup: { ...setup, capacity_mode: 'finite', total_system_capacity: 15, abandonment_mode: 'modeled', patience_rate_per_hour: 0.5 } }))
  })

  it('merges into fresh Setup and refreshes compatibility and stale evidence', async () => {
    const client = makeQueryClient()
    const latest: QueueSetup = { ...setup, fixed_server_count: 8, segments: [{ id: 'late', start_time: '08:00', end_time: '10:00', active_queue_ids: null }], counter_breaks: [{ scheduled_start_time: '09:00', duration_minutes: 15 }] }
    mocks.get.mockResolvedValueOnce(project()).mockResolvedValue(project(latest))
    const invalidate = vi.spyOn(client, 'invalidateQueries')
    const reset = vi.spyOn(client, 'resetQueries')
    renderWithProviders(editor(), { queryClient: client })
    const user = await supported()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await screen.findByText('Queue setup saved.')
    expect(mocks.patch).toHaveBeenCalledWith(7, { queue_setup: { ...latest, capacity_mode: 'unlimited', abandonment_mode: 'not_modeled' } })
    expect(mocks.get.mock.invocationCallOrder[1]).toBeLessThan(mocks.patch.mock.invocationCallOrder[0])
    for (const prefix of ['current', 'continuous-compat', 'continuous-runs', 'continuous-run']) expect(invalidate).toHaveBeenCalledWith({ queryKey: [prefix, 7] })
    for (const prefix of ['workflow', 'scenarios']) expect(reset).toHaveBeenCalledWith({ queryKey: [prefix, 7] })
    await waitFor(() => expect(saving).toHaveBeenLastCalledWith(false))
  })

  it('preserves a failed draft and prevents duplicate saves while pending', async () => {
    let reject!: (reason: unknown) => void
    const pending = new Promise((_, fail) => { reject = fail })
    mocks.patch.mockReturnValue(pending)
    renderWithProviders(editor())
    const user = await supported()
    await user.dblClick(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledTimes(1))
    expect(saving).toHaveBeenLastCalledWith(true)
    expect(screen.getByRole('radio', { name: 'No known limit' })).toBeDisabled()
    await act(async () => { reject({ response: { data: { detail: 'Save refused.' } } }); await pending.catch(() => {}) })
    expect(await screen.findByRole('alert')).toHaveTextContent('Save refused.')
    expect(screen.getByRole('radio', { name: 'No known limit' })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Save' })).toBeEnabled()
    expect(saving).toHaveBeenLastCalledWith(true)
    expect(screen.queryByText('Queue setup saved.')).not.toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'Cancel' }))
    expect(saving).toHaveBeenLastCalledWith(false)
  })

  it('does not write if the required fresh read fails', async () => {
    mocks.get.mockResolvedValueOnce(project()).mockRejectedValue({ response: { data: { detail: 'Read refused.' } } })
    renderWithProviders(editor())
    const user = await supported()
    await user.click(screen.getByRole('button', { name: 'Save' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Read refused.')
    expect(mocks.patch).not.toHaveBeenCalled()
  })

  it('shows a read failure without exposing editable choices', async () => {
    mocks.get.mockRejectedValue(new Error('Read failed'))
    renderWithProviders(editor())
    await screen.findByRole('alert')
    expect(screen.queryByRole('radio')).not.toBeInTheDocument()
    expect(mocks.patch).not.toHaveBeenCalled()
  })

  it('resets drafts on analysis changes and only saves the new analysis', async () => {
    mocks.get.mockImplementation(async (id: number) => project(setup, id))
    const { rerender } = renderWithProviders(editor())
    const user = await supported()
    rerender(editor(8))
    expect(await screen.findByRole('radio', { name: "I'm not sure" })).toBeChecked()
    expect(screen.getByRole('button', { name: 'Save' })).toBeDisabled()
    await user.click(screen.getByRole('radio', { name: 'No known limit' }))
    await user.click(screen.getByRole('button', { name: 'Save' }))
    await waitFor(() => expect(mocks.patch).toHaveBeenCalledWith(8, { queue_setup: { ...setup, capacity_mode: 'unlimited' } }))
    expect(mocks.patch).toHaveBeenCalledTimes(1)
  })

  it.each([false, true])('prevents editing during a run or for archived analyses (%s)', async (archived) => {
    if (archived) mocks.get.mockResolvedValue({ analysis: { ...project().analysis, archived_at: '2026-10-30' } })
    renderWithProviders(editor(7, !archived))
    expect(await screen.findByRole('radio', { name: 'No known limit' })).toBeDisabled()
    expect(mocks.patch).not.toHaveBeenCalled()
  })

  it('uses the existing Filipino choices and unknown-answer note', async () => {
    renderWithProviders(editor(), { lang: 'tl' })
    expect(await screen.findByRole('radio', { name: 'Hindi ako sigurado' })).toBeChecked()
    expect(screen.getByText("Puwede kang mag-save ngayon. Hindi magagamit ang takbo ng buong araw hangga't hindi ka sumasagot.")).toBeInTheDocument()
    expect(mocks.patch).not.toHaveBeenCalled()
  })
})
