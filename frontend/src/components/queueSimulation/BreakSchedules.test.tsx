import { screen } from '@testing-library/react'
import { describe, expect, it, vi } from 'vitest'
import type { AnalysisProjectOut, QueueBreak, SimulationTrace } from '../../api/types'
import type { WorkflowEvidence } from '../../api/workflow'
import { renderWithProviders } from '../../test/test-utils'
import { ReplayView } from './ReplayView'
import { buildContext, currentModelsBreaks, currentNoBreaksChip, runBasisKey, runSetup } from './simulationContext'

vi.mock('../simulation/SeparateSimulationPlayback', () => ({
  SeparateSimulationPlayback: ({ scheduled }: { scheduled: unknown }) =>
    <output data-testid="replay-schedule">{JSON.stringify(scheduled)}</output>,
}))
vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({ user: { id: 1, email: 'test@example.com', role: 'admin', active: true } })),
  logout: vi.fn(async () => ({})),
}))

const baseline: QueueBreak[] = [{ queue_id: 'a', break_name: 'Lunch', scheduled_start_time: '08:15', duration_minutes: 15 }]
const proposed: QueueBreak[] = [{ ...baseline[0], scheduled_start_time: '08:30' }]
const trace: SimulationTrace = {
  trace: [], trace_hours: 1, total_hours: 1, event_count: 0, truncated: false,
  abandonment_supported: false, segments: [], break_policy: 'scheduled_windows_nonpreemptive_v1',
}

function context(planBreaks: QueueBreak[] | undefined = proposed, current: SimulationTrace | null = trace) {
  const analysis = {
    id: 7, queue_setup: {
      queue_structure: 'separate_queues', queue_ids: ['a'], fixed_server_count: 1,
      staffing_varies_by_period: false, capacity_mode: 'unlimited', abandonment_mode: 'not_modeled',
      event_period_basis: 'representative_day', breaks: structuredClone(baseline),
      separate_queue_closure_policy: 'drain_existing',
      segments: [{ id: 's1', start_time: '08:00', end_time: '09:00' }],
    },
  } as AnalysisProjectOut
  const scenario = { id: 9, name: 'Suggested', settings: { calculation: { schema_version: 2, plan_breaks: planBreaks } } }
  const workflow = {
    scenario, des_current: current === null ? null : { id: 1, result: current },
    des: { id: 2, result: {
      provenance: 'SELECTED', scenario_id: 9,
      periods: [{ time: 's1', start_hours: 0, duration_hours: 1, inactive_queue_ids: [], trace }],
    } },
  } as unknown as WorkflowEvidence
  return buildContext(7, analysis, workflow)
}

describe('Current and Suggested break schedules', () => {
  it('resolves each saved plan without changing the baseline', () => {
    const first = context()
    expect(runSetup(first, 'current').breaks).toEqual(baseline)
    expect(runSetup(first, 'suggested').breaks).toEqual(proposed)
    const second = context([{ ...proposed[0], scheduled_start_time: '08:45' }])
    expect(runSetup(second, 'suggested').breaks?.[0].scheduled_start_time).toBe('08:45')
    expect(first.analysis.queue_setup.breaks).toEqual(baseline)
    expect(second.analysis.queue_setup.breaks).toEqual(baseline)
  })

  it('keeps legacy plans on their original baseline schedule', () => {
    const value = context()
    delete (value.scenario!.settings!.calculation as { plan_breaks?: unknown }).plan_breaks
    expect(runSetup(value, 'suggested')).toBe(value.analysis.queue_setup)
  })

  it('marks only new Current executions as break aware', () => {
    const value = context()
    expect(currentModelsBreaks(value)).toBe(true)
    expect(runBasisKey(value, 'current')).toBe('simulation.run_basis_baseline_breaks')
    expect(currentNoBreaksChip(value, 'current')).toBe(false)
    expect(currentModelsBreaks(context(proposed, { ...trace, break_policy: undefined }))).toBe(false)
    expect(currentModelsBreaks(context(proposed, null))).toBe(true)
  })

  it('supplies saved Suggested breaks to replay while Current receives baseline breaks', () => {
    const value = context()
    const view = renderWithProviders(<ReplayView context={value} run="suggested" />)
    expect(screen.getByTestId('replay-schedule')).toHaveTextContent('"startHours":0.5')
    view.rerender(<ReplayView context={value} run="current" />)
    expect(screen.getByTestId('replay-schedule')).toHaveTextContent('"startHours":0.25')
    expect(value.analysis.queue_setup.breaks).toEqual(baseline)
  })
})
