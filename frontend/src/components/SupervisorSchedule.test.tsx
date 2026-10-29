import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { OptimizePage } from '../pages/OptimizePage'
import type { SupervisorPreview } from '../api/optimization'

const mocks = vi.hoisted(() => ({ preview: vi.fn(), apply: vi.fn(), analysis: vi.fn(),
  files: vi.fn(), save: vi.fn(), select: vi.fn() }))
vi.mock('../api/analyses', () => ({ getAnalysis: mocks.analysis }))
vi.mock('../api/datasets', () => ({ listDatasets: mocks.files, getDataset: vi.fn() }))
vi.mock('../api/scenarios', () => ({ createScenario: mocks.save }))
vi.mock('../api/workflow', () => ({ selectWorkflowScenario: mocks.select }))
vi.mock('../api/optimization', async importOriginal => ({
  ...await importOriginal<typeof import('../api/optimization')>(),
  previewSupervisorSchedule: mocks.preview, applySupervisorSchedule: mocks.apply,
}))
vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'fixture@example.com', role: 'admin', active: true } })),
  login: vi.fn(), logout: vi.fn(),
}))
const setup = { queue_structure: 'separate_queues', queue_ids: ['a','b'],
  event_period_basis: 'representative_day', breaks: [{ queue_id: 'a', scheduled_start_time: '10:00:00', duration_minutes: 30 }] }
const analysis = { id: 7, name: 'Synthetic screen fixture', queue_setup: setup }
const file = { id: 1, name: 'Planning fixture', row_count: 50, validation: { ok: true }, purpose: 'planning' }
function preview(moves = false): SupervisorPreview {
  return {
    engine_version: 'fixture-engine', preview_hash: 'a'.repeat(64), setup_hash: 'setup', dataset_id: 1,
    can_apply: moves, blockers: moves ? [] : ['break_changes_off'],
    schedule: { overall: 'COMPLETE', reason: null, target_utilization: .7,
      evaluation_method: 'DES_REPLICATIONS', des: { replications: 20, base_seed: 42, duration_hours: 24, max_events: 10000 },
      periods: [{ time: '08:00-09:00', overall: 'OPTIMAL', reason: null, current_active_lanes: ['a','b'],
        optimal_active_lanes: 2, adjustment: 0, candidates: [], evaluation_method: 'DES_REPLICATIONS',
        optimum: { active_lane_count: 2, recommendation: 'KEEP', total_cost: 100, candidate_utilization: .6 } }] },
    breaks: moves ? {
      status: 'improved', target_rho: .7, max_shift_minutes: 120, all_below_target: true,
      current_breaks: [], proposed_breaks: [], moves: [{ queue_id: 'a', label: 'Break 1', from: '10:00', to: '11:00', duration_minutes: 30 }],
      slots: [{ start: '10:00', end: '10:15', lambda: 10, mu: 10, working_before: 1, working_after: 2, rho_before: 1, rho_after: .5 }],
      peak_rho: { before: 1, after: .5 }, slots_above_target: { before: 1, after: 0 },
      staffing_gaps: [], passes: 2, pass_cap_reached: false, pass_peak_rho: [.5, .5], notes: [],
      des: { seeds: [42,43,44,45,46],
        current: { summary: { mean_wait_minutes: 2, max_queue: 3, admitted: 50, served: 50, customer_conservation: true }, periods: [], replications: [] },
        proposed: { summary: { mean_wait_minutes: 1, max_queue: 2, admitted: 50, served: 50, customer_conservation: true }, periods: [], replications: [] },
        comparison: { mean_wait_change_minutes: -1, proposed_better_runs: 4, runs: 5,
          paired_wait_change: { mean: -1, sd: 1, se: .4, ci_lower: -2.1, ci_upper: .1, n: 5, verdict: 'no_clear_difference' } } },
    } : null,
  }
}
function render() {
  return renderWithProviders(<Routes><Route path="/analyses/:analysisId/plans" element={<OptimizePage />} /></Routes>,
    { route: '/analyses/7/plans' })
}
async function run(breaks = false) {
  const user = userEvent.setup()
  await screen.findByRole('heading', { name: 'Suggested Schedule' })
  if (breaks) await user.click(screen.getByRole('checkbox', { name: 'Allow break times to change' }))
  await user.click(screen.getByRole('button', { name: 'Check schedule' }))
  await screen.findByRole('heading', { name: 'Review the Check' })
  return user
}
async function confirm(user: ReturnType<typeof userEvent.setup>) {
  await user.click(screen.getByRole('button', { name: 'Continue to confirm' }))
  expect(screen.getByRole('tabpanel', { name: 'Confirm' })).toBeVisible()
}
beforeEach(() => {
  vi.clearAllMocks()
  mocks.analysis.mockResolvedValue({ analysis })
  mocks.files.mockResolvedValue({ datasets: [file] })
  mocks.preview.mockImplementation(async (_id, request) => preview(request.allow_break_changes))
  mocks.save.mockResolvedValue({ scenario: { id: 9 } })
  mocks.select.mockResolvedValue({})
  mocks.apply.mockImplementation(async () => {
    const updated = { ...analysis, queue_setup: { ...setup, breaks: [{ ...setup.breaks[0], scheduled_start_time: '11:00:00' }] } }
    mocks.analysis.mockResolvedValue({ analysis: updated })
    return { ...preview(true), can_apply: false, analysis: updated, moves_applied: 1 }
  })
})
describe('supervisor schedule workflow', () => {
  it('starts at 70%, leaves breaks off, and does not calculate on page load', async () => {
    render()
    expect(await screen.findByRole('spinbutton', { name: 'Busy limit per cashier' })).toHaveValue(70)
    expect(screen.getByRole('checkbox')).not.toBeChecked()
    expect(mocks.preview).not.toHaveBeenCalled()
  })
  it('shows exactly one panel, including honest placeholders before checking', async () => {
    render(); const user = userEvent.setup()
    await screen.findByRole('spinbutton', { name: 'Busy limit per cashier' })
    for (const name of ['Review', 'Confirm', 'Settings']) {
      await user.click(screen.getByRole('tab', { name }))
      expect(screen.getAllByRole('tabpanel')).toHaveLength(1)
      expect(screen.getByRole('tabpanel', { name })).toBeVisible()
      expect(screen.getAllByRole('tabpanel', { hidden: true }).filter(panel => panel.hidden)).toHaveLength(2)
      expect(screen.getByRole('tab', { name })).toHaveAttribute('aria-selected', 'true')
      if (name !== 'Settings') {
        expect(within(screen.getByRole('tabpanel')).getByText(/Go to Settings and check/)).toBeVisible()
        expect(screen.queryByRole('spinbutton')).not.toBeInTheDocument()
        expect(screen.queryByRole('button', { name: 'Use this Plan' })).not.toBeInTheDocument()
      }
    }
    expect(mocks.preview).not.toHaveBeenCalled()
    expect(mocks.apply).not.toHaveBeenCalled()
    expect(mocks.save).not.toHaveBeenCalled()
    expect(mocks.select).not.toHaveBeenCalled()
  })
  it('supports keyboard tabs with one tab stop, and hides the old controls from focus', async () => {
    render(); const user = userEvent.setup()
    const settings = await screen.findByRole('tab', { name: 'Settings' })
    settings.focus()
    await user.keyboard('{ArrowRight}')
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Review' })).toHaveFocus())
    expect(screen.getByRole('tabpanel', { name: 'Review' })).toBeVisible()
    expect(settings).toHaveAttribute('tabindex', '-1')
    await user.keyboard('{End}')
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Confirm' })).toHaveFocus())
    await user.keyboard('{ArrowRight}')
    await waitFor(() => expect(settings).toHaveFocus())
    await user.keyboard('{ArrowLeft}')
    await waitFor(() => expect(screen.getByRole('tab', { name: 'Confirm' })).toHaveFocus())
    await user.keyboard('{Home}')
    await waitFor(() => expect(settings).toHaveFocus())
    expect(screen.getAllByRole('tab').filter(tab => tab.tabIndex === 0)).toHaveLength(1)
    expect(mocks.preview).not.toHaveBeenCalled()
  })
  it('retains draft fields and review evidence across all three tabs without extra requests', async () => {
    render(); const user = userEvent.setup()
    const percent = await screen.findByRole('spinbutton', { name: 'Busy limit per cashier' })
    await user.clear(percent); await user.type(percent, '72.5')
    await run(true)
    expect(screen.queryByRole('spinbutton', { name: 'Busy limit per cashier' })).not.toBeInTheDocument()
    await confirm(user)
    await user.type(screen.getByLabelText('Scenario Name'), ' draft')
    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    expect(percent).toHaveValue(72.5)
    expect(screen.getByRole('checkbox')).toBeChecked()
    await user.click(screen.getByRole('tab', { name: 'Review' }))
    expect(screen.getByText(/No clear change in wait/)).toBeVisible()
    await confirm(user)
    expect(screen.getByLabelText('Scenario Name')).toHaveValue('Schedule at 72.5% draft')
    expect(mocks.preview).toHaveBeenCalledTimes(1)
    expect(mocks.apply).not.toHaveBeenCalled()
    expect(mocks.save).not.toHaveBeenCalled()
  })
  it('names the plan after the checked busy limit until the user types a name', async () => {
    render(); const user = await run()
    async function recheck(value: string) {
      await user.click(screen.getByRole('tab', { name: 'Settings' }))
      const percent = screen.getByRole('spinbutton', { name: 'Busy limit per cashier' })
      await user.clear(percent); await user.type(percent, value)
      await user.click(screen.getByRole('button', { name: 'Check schedule' }))
      await screen.findByRole('heading', { name: 'Review the Check' })
      await confirm(user)
    }
    await confirm(user)
    expect(screen.getByLabelText('Scenario Name')).toHaveValue('Schedule at 70%')
    await recheck('75')
    expect(screen.getByLabelText('Scenario Name')).toHaveValue('Schedule at 75%')
    await user.clear(screen.getByLabelText('Scenario Name'))
    await user.type(screen.getByLabelText('Scenario Name'), 'Saturday rush')
    await recheck('80')
    expect(screen.getByLabelText('Scenario Name')).toHaveValue('Saturday rush')
    await user.clear(screen.getByLabelText('Scenario Name'))
    await recheck('85')
    expect(screen.getByLabelText('Scenario Name')).toHaveValue('Schedule at 85%')
  })
  it('gives the review step room above the sticky step bar', async () => {
    const { container } = render(); await run(true)
    expect(container.querySelector('.supervisor-page .supervisor-break-table table caption'))
      .toHaveTextContent('Break Changes to Review')
    const css = readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8')
    expect(css).toMatch(/html:has\(\.supervisor-page\)\s*\{\s*scroll-padding-bottom:/)
    expect(css).toMatch(/\.supervisor-page \.supervisor-break-table caption\s*\{\s*padding: var\(--space-md\)/)
  })
  it('moves the slider by five points while preserving typed fractional values', async () => {
    const user = userEvent.setup(); render()
    const input = await screen.findByRole('spinbutton', { name: 'Busy limit per cashier' })
    await user.clear(input); await user.type(input, '72.5')
    expect(screen.getByRole('slider')).toHaveValue('72.5')
    await user.click(screen.getByRole('button', { name: 'Check schedule' }))
    expect(mocks.preview).toHaveBeenCalledWith(7, expect.objectContaining({ target_utilization: .725, des: { base_seed: 42 }, min_active_lanes: 2 }))
    await screen.findByRole('heading', { name: 'Review the Check' })
    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    screen.getByRole('slider').focus()
    await user.keyboard('{ArrowRight}')
    expect(input).toHaveValue(77.5)
    await user.keyboard('{End}')
    expect(input).toHaveValue(90)
    fireEvent.change(screen.getByRole('slider'), { target: { value: '72.4' } })
    expect(input).toHaveValue(70)
  })
  it.each(['', '39', '91'])('does not request a check for invalid percentage %s', async value => {
    const user = userEvent.setup(); render()
    const input = await screen.findByRole('spinbutton', { name: 'Busy limit per cashier' })
    await user.clear(input); if (value) await user.type(input, value)
    await user.click(screen.getByRole('button', { name: 'Check schedule' }))
    const alert = await screen.findByRole('alert')
    await waitFor(() => expect(alert).toHaveFocus())
    expect(mocks.preview).not.toHaveBeenCalled()
  })
  it('shows a real combined preview, wait uncertainty and disables saving unapplied moves', async () => {
    render(); const user = await run(true)
    expect(mocks.preview).toHaveBeenCalledWith(7, expect.objectContaining({ allow_break_changes: true, max_shift_minutes: 120 }))
    expect(screen.getByText(/No clear change in wait/)).toBeVisible()
    expect(screen.getByRole('table', { name: 'Break Changes to Review' })).toHaveTextContent('11:00')
    await confirm(user)
    expect(screen.getByRole('button', { name: 'Use this Plan' })).toBeDisabled()
    expect(mocks.apply).not.toHaveBeenCalled()
  })
  it('Back and Escape return to Review, restore focus and never apply', async () => {
    render(); const user = await run(true)
    const trigger = screen.getByRole('button', { name: 'Continue to confirm' })
    await user.click(trigger)
    await user.keyboard('{Escape}')
    await waitFor(() => expect(trigger).toHaveFocus())
    await user.click(trigger)
    await user.click(screen.getByRole('button', { name: 'Back to Review' }))
    await waitFor(() => expect(trigger).toHaveFocus())
    expect(mocks.apply).not.toHaveBeenCalled()
  })
  it('rechecks before saving, refreshes evidence and permits verified snapshot save only after applying', async () => {
    const view = render(); const user = await run(true)
    view.queryClient.setQueryData(['workflow',7], { old: true })
    await confirm(user)
    await user.click(screen.getByRole('button', { name: 'Save break changes' }))
    expect(await screen.findByText(/Break times saved in Setup/)).toBeVisible()
    expect(mocks.apply).toHaveBeenCalledWith(7, expect.objectContaining({ preview_hash: 'a'.repeat(64), target_utilization: .7 }))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Use this Plan' })).toBeEnabled())
    expect(view.queryClient.getQueryData(['workflow',7])).toBeUndefined()
    await user.click(screen.getByRole('button', { name: 'Use this Plan' }))
    expect(mocks.save).toHaveBeenCalledWith(expect.objectContaining({
      dataset_id: 1, settings: expect.objectContaining({ min_active_lanes: 2, calculation: expect.objectContaining({
        schema_version: 2, engine_version: 'fixture-engine', dataset_row_count: 50,
      }) }),
    }))
    expect(mocks.select).toHaveBeenCalledWith(7,9)
  })
  it.each(['staffing_check','break_limit','wait_longer','wait_unavailable','not_current_data','customer_accounting'] as const)(
    'blocks save and apply when %s fails', async blocker => {
      const value = preview(true); value.can_apply = false; value.blockers = [blocker]
      mocks.preview.mockResolvedValue(value)
      render(); const user = await run(true); await confirm(user)
      expect(screen.getByRole('button', { name: 'Save break changes' })).toBeDisabled()
      expect(screen.getByRole('button', { name: 'Use this Plan' })).toBeDisabled()
    })
  it('permits the unchanged checked plan when no break moves are found', async () => {
    const value = preview(true); value.can_apply = false; value.blockers = ['no_moves']; value.breaks!.moves = []
    mocks.preview.mockResolvedValue(value)
    render(); const user = await run(true); await confirm(user)
    expect(screen.queryByRole('button', { name: 'Save break changes' })).not.toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Save without using' })).toBeEnabled()
  })
  it('makes input changes stale and blocks all persistence', async () => {
    render(); const user = await run(true)
    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    await user.clear(screen.getByRole('spinbutton', { name: 'Busy limit per cashier' }))
    await user.type(screen.getByRole('spinbutton', { name: 'Busy limit per cashier' }), '75')
    expect(screen.getByRole('alert')).toHaveTextContent(/Check the schedule again/)
    await user.click(screen.getByRole('tab', { name: 'Confirm' }))
    expect(screen.getByRole('button', { name: 'Save break changes' })).toBeDisabled()
  })
  it('does not show stale async results as applicable after a setup refresh', async () => {
    let finish!: (value: SupervisorPreview) => void
    mocks.preview.mockImplementation(() => new Promise<SupervisorPreview>(resolve => { finish = resolve }))
    const view = render(); const user = userEvent.setup()
    await screen.findByRole('heading', { name: 'Suggested Schedule' })
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByRole('button', { name: 'Check schedule' }))
    view.queryClient.setQueryData(['analysis',7], { analysis: { ...analysis, queue_setup: { ...setup, breaks: [] } } })
    finish(preview(true))
    await screen.findByRole('heading', { name: 'Review the Check' })
    await confirm(user)
    expect(screen.getByRole('button', { name: 'Save break changes' })).toBeDisabled()
  })
  it('discards a refused apply and preserves the server message', async () => {
    mocks.apply.mockRejectedValue({ response: { data: { detail: 'Setup changed; check again.' } } })
    render(); const user = await run(true)
    await confirm(user)
    await user.click(screen.getByRole('button', { name: 'Save break changes' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Setup changed; check again.')
    expect(screen.queryByRole('button', { name: 'Use this Plan' })).not.toBeInTheDocument()
  })
  it('keeps a saved plan and explains a refused selection', async () => {
    mocks.select.mockRejectedValue({ response: { data: { detail: 'Selection refused' } } })
    render(); const user = await run()
    await confirm(user)
    await user.click(screen.getByRole('button', { name: 'Use this Plan' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Selection refused')
    expect(mocks.save).toHaveBeenCalledTimes(1)
  })
  it('does not select when saving fails', async () => {
    mocks.save.mockRejectedValue(new Error('save failed'))
    render(); const user = await run()
    await confirm(user)
    await user.click(screen.getByRole('button', { name: 'Use this Plan' }))
    await screen.findByRole('alert')
    expect(mocks.select).not.toHaveBeenCalled()
  })
  it('leaves review-only files out even when newer, and keeps the user choice', async () => {
    mocks.files.mockResolvedValue({ datasets: [file, { ...file, id: 2, name: 'Other planning' }, { ...file, id: 3, name: 'Review only', purpose: 'review' }] })
    render(); const user = await run()
    await user.click(screen.getByRole('tab', { name: 'Settings' }))
    expect(screen.queryByRole('option', { name: 'Review only' })).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Source dataset'), '1')
    expect(screen.getByLabelText('Source dataset')).toHaveValue('1')
  })
  it('rejects mixed demand assumptions when breaks are enabled', async () => {
    render(); const user = userEvent.setup()
    await screen.findByRole('heading', { name: 'Suggested Schedule' })
    await user.click(screen.getByRole('checkbox'))
    await user.click(screen.getByText('Assumptions and limits'))
    await user.clear(screen.getByLabelText('Customer demand multiplier')); await user.type(screen.getByLabelText('Customer demand multiplier'), '2')
    await user.click(screen.getByRole('button', { name: 'Check schedule' }))
    await screen.findByRole('alert')
    expect(mocks.preview).not.toHaveBeenCalled()
  })
  it('keeps missing metrics unavailable and shows flagged near-target evidence', async () => {
    const value = preview(false)
    value.schedule.periods[0].optimum = { ...value.schedule.periods[0].optimum!, near_target_noise: true, total_cost: null }
    mocks.preview.mockResolvedValue(value)
    render(); const user = await run()
    await user.click(screen.getByText('Schedule and calculation details'))
    expect(screen.getByText(/within simulation noise/)).toBeVisible()
    expect(within(screen.getAllByRole('table')[0]).getByText('—')).toBeInTheDocument()
  })
})
