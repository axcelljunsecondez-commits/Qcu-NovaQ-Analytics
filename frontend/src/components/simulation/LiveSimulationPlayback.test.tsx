import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { SimulationTrace } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import { LiveSimulationPlayback } from './LiveSimulationPlayback'

function makeTrace(arrivals: number): SimulationTrace {
  return {
    trace: Array.from({ length: arrivals }, (_, index) => ({
      t: 0.1,
      type: 'arrival' as const,
      segment_id: 0,
      customer_id: index + 1,
      server_id: null,
      queue_len_after: index + 1,
    })),
    trace_hours: 1,
    total_hours: 1,
    event_count: arrivals,
    truncated: false,
    abandonment_supported: false,
    segments: [{
      segment_id: 0,
      time: '08:00-09:00',
      lambda: arrivals,
      mu: 1,
      c: 1,
      selected_model: 'M/M/1',
      simulation_supported: true,
      error: null,
      queue_structure: 'shared',
      initial_queue_depth: 0,
      final_queue_depth: arrivals,
    }],
  }
}

describe('LiveSimulationPlayback', () => {
  it('renders a supported zero-arrival environment without inventing customers', () => {
    renderWithProviders(<LiveSimulationPlayback trace={makeTrace(0)} />)
    expect(screen.getByText('Shared queue')).toBeInTheDocument()
    expect(screen.getByText('Queue is empty')).toBeInTheDocument()
    expect(screen.getByText('No arrivals yet')).toBeInTheDocument()
    expect(screen.queryByText('Abandoned exit')).not.toBeInTheDocument()
  })

  it('bounds heavy-queue customer tokens while preserving the real count', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LiveSimulationPlayback trace={makeTrace(10)} />)
    await user.click(screen.getByRole('button', { name: 'Step' }))
    expect(screen.getByText('Waiting: 10')).toBeInTheDocument()
    expect(screen.getByText('+2')).toBeInTheDocument()
    expect(screen.getByText(/Arrived 10 = served 0 \+ waiting 10 \+ serving 0/)).toBeInTheDocument()
  })
})
