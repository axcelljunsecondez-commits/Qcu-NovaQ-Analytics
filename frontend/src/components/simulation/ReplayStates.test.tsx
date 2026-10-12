import { describe, expect, it, vi } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import type { SimulationTrace, SimulationTraceEvent } from '../../api/types'
import { SeparateSimulationPlayback } from './SeparateSimulationPlayback'

// B5 / D26: counter states in the separate-lines replay come from the run's own events.

function event(t: number, type: SimulationTraceEvent['type'], customer: number | null, queue = 'a'): SimulationTraceEvent {
  return { t, type, segment_id: 's1', customer_id: customer as number, server_id: `server:${queue}`, queue_len_after: 0, queue_id: queue }
}

function trace(events: SimulationTraceEvent[], truncated = false): SimulationTrace {
  return {
    trace: events, trace_hours: 2, total_hours: 2, event_count: events.length, truncated, abandonment_supported: false,
    segments: ['a', 'b'].map((queue) => ({ segment_id: `s1:${queue}`, time: 's1', queue_id: queue, server_id: `server:${queue}`, lambda: 4, mu: 6, c: 1,
      selected_model: 'Parallel M/G/1 (routing)', simulation_supported: true, error: null, queue_structure: 'separate' as const, initial_queue_depth: 0, final_queue_depth: 0 })),
  }
}

const withBreak = trace([
  event(0.1, 'arrival', 1), event(0.2, 'service_start', 1), event(0.5, 'draining_start', null),
  event(0.6, 'service_end', 1), event(0.6, 'break_start', null), event(1.1, 'break_end', null),
])

describe('separate-lines replay states', () => {
  it('shows Finishing customers before break, On break and Available at the run\'s event times', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={withBreak} originMinutes={480} />)
    const goTo = screen.getByLabelText('Go to time')
    for (const [clock, state] of [['08:33', 'Finishing customers before break'], ['08:40', 'On break'], ['09:10', 'Available']]) {
      fireEvent.change(goTo, { target: { value: clock } })
      await user.click(screen.getByRole('button', { name: 'Go' }))
      expect(screen.getByTestId('replay-clock')).toHaveTextContent(clock)
      expect(screen.getByTestId('state-a')).toHaveTextContent(state)
    }
    expect(screen.getByTestId('state-b')).toHaveTextContent('Available')
  })

  it('shows Closed / not staffed only from the plan\'s staffing, never as a break', () => {
    renderWithProviders(<SeparateSimulationPlayback trace={trace([event(0.1, 'arrival', 1)])} inactiveQueueIds={['b']} />)
    expect(screen.getByTestId('state-b')).toHaveTextContent('Closed / not staffed')
    expect(screen.queryByText('On break')).not.toBeInTheDocument()
  })

  it('lists scheduled breaks on their own row and says when the run has no break events', () => {
    const scheduled = [{ queueId: 'a', startHours: 0.5, endHours: 1, name: null }]
    renderWithProviders(<SeparateSimulationPlayback trace={trace([event(0.1, 'arrival', 1)])} originMinutes={480} scheduled={scheduled} />)
    expect(screen.getByRole('group', { name: 'Scheduled break (from your setup)' })).toHaveTextContent('a: 08:30–09:00')
    expect(screen.getByText('Break state unavailable for this run.')).toBeInTheDocument()
  })

  it('does not claim missing break states when the run recorded them', () => {
    const scheduled = [{ queueId: 'a', startHours: 0.5, endHours: 1, name: null }]
    renderWithProviders(<SeparateSimulationPlayback trace={withBreak} originMinutes={480} scheduled={scheduled} />)
    expect(screen.queryByText('Break state unavailable for this run.')).not.toBeInTheDocument()
  })

  it('says where a cut-short replay stops', () => {
    renderWithProviders(<SeparateSimulationPlayback trace={trace([event(0.1, 'arrival', 1), event(0.75, 'arrival', 2)], true)} originMinutes={480} />)
    expect(screen.getByTestId('replay-cut-short')).toHaveTextContent('The replay stops at 08:45. The summary still covers the whole run.')
  })

  it('refuses a time outside the run and reports the chosen time when paused', async () => {
    const onTimeChange = vi.fn()
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={withBreak} originMinutes={480} onTimeChange={onTimeChange} />)
    fireEvent.change(screen.getByLabelText('Go to time'), { target: { value: '07:00' } })
    await user.click(screen.getByRole('button', { name: 'Go' }))
    expect(screen.getByRole('alert')).toHaveTextContent('Enter a time within the run.')
    fireEvent.change(screen.getByLabelText('Go to time'), { target: { value: '08:45' } })
    await user.click(screen.getByRole('button', { name: 'Go' }))
    expect(onTimeChange).toHaveBeenLastCalledWith(0.75)
  })
})
