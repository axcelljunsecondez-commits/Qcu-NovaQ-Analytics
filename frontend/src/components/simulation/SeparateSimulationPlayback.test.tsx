import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { SimulationTrace } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import { SeparateSimulationPlayback } from './SeparateSimulationPlayback'

function makeSeparateTrace(): SimulationTrace {
  return {
    trace: [
      { t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_len_after: 1, queue_id: 'Q1' },
      { t: 0.1, type: 'service_start', segment_id: 's1', customer_id: 1, server_id: 'server:Q1', queue_len_after: 0, queue_id: 'Q1' },
      { t: 0.2, type: 'arrival', segment_id: 's1', customer_id: 2, server_id: null, queue_len_after: 1, queue_id: 'Q2' },
      { t: 0.2, type: 'service_start', segment_id: 's1', customer_id: 2, server_id: 'server:Q2', queue_len_after: 0, queue_id: 'Q2' },
      { t: 0.4, type: 'service_end', segment_id: 's1', customer_id: 1, server_id: 'server:Q1', queue_len_after: 0, queue_id: 'Q1' },
    ],
    trace_hours: 1,
    total_hours: 1,
    event_count: 5,
    truncated: false,
    abandonment_supported: false,
    segments: [
      {
        segment_id: 's1',
        time: '08:00-09:00',
        lambda: 5,
        mu: 4,
        c: 1,
        selected_model: 'Parallel M/G/1',
        simulation_supported: true,
        error: null,
        queue_structure: 'separate',
        initial_queue_depth: 0,
        final_queue_depth: 0,
      },
    ],
  }
}

describe('SeparateSimulationPlayback', () => {
  it('keeps Q1 events in Q1 lane', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={makeSeparateTrace()} />)
    // Step twice to include Q1 (t=0.1) and Q2 (t=0.2) events; presentation-only.
    await user.click(screen.getByRole('button', { name: 'Step' }))
    await user.click(screen.getByRole('button', { name: 'Step' }))
    expect(screen.getByTestId('lane-Q1')).toContainElement(screen.getByTestId('customer-1'))
    expect(screen.getByTestId('lane-Q2')).toContainElement(screen.getByTestId('customer-2'))
    expect(screen.getByTestId('lane-Q1')).not.toContainElement(screen.getByTestId('customer-2'))
  })

  it('preserves dedicated server identity per queue without pooling', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={makeSeparateTrace()} />)
    await user.click(screen.getByRole('button', { name: 'Step' }))
    await user.click(screen.getByRole('button', { name: 'Step' }))
    expect(screen.getByTestId('server-server:Q1')).toBeInTheDocument()
    expect(screen.getByTestId('server-server:Q2')).toBeInTheDocument()
  })
})
