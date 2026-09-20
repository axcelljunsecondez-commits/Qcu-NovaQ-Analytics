import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it } from 'vitest'
import type { SimulationTrace } from '../../api/types'
import { renderWithProviders } from '../../test/test-utils'
import { SeparateSimulationPlayback } from './SeparateSimulationPlayback'

function makeTrace(): SimulationTrace {
  return {
    trace: [
      { t: 0.1, type: 'arrival', segment_id: 's1', customer_id: 1, server_id: null, queue_len_after: 1, queue_id: 'Q1' },
      { t: 0.1, type: 'service_start', segment_id: 's1', customer_id: 1, server_id: 'server:Q1', queue_len_after: 0, queue_id: 'Q1' },
      { t: 0.2, type: 'arrival', segment_id: 's1', customer_id: 2, server_id: null, queue_len_after: 1, queue_id: 'Q1' },
      { t: 0.3, type: 'arrival', segment_id: 's1', customer_id: 3, server_id: null, queue_len_after: 1, queue_id: 'Q2' },
    ],
    trace_hours: 1,
    total_hours: 1,
    event_count: 4,
    truncated: false,
    abandonment_supported: false,
    segments: [
      {
        segment_id: 's1:Q1',
        time: '08:00-09:00',
        queue_id: 'Q1',
        server_id: 'server:Q1',
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
      {
        segment_id: 's1:Q2',
        time: '08:00-09:00',
        queue_id: 'Q2',
        server_id: 'server:Q2',
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
      {
        segment_id: 's1:Q3',
        time: '08:00-09:00',
        queue_id: 'Q3',
        server_id: 'server:Q3',
        lambda: 0,
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

function makeWideTrace(laneCount: number): SimulationTrace {
  const base = makeTrace()
  return {
    ...base,
    // Layout only: the lanes come from the run's declared segments, not events.
    trace: [],
    event_count: 0,
    segments: Array.from({ length: laneCount }, (_, index) => ({
      ...base.segments[0],
      segment_id: `s1:W${index + 1}`,
      queue_id: `W${index + 1}`,
      server_id: `server:W${index + 1}`,
    })),
  }
}

async function stepTo(user: ReturnType<typeof userEvent.setup>, times: number) {
  for (let index = 0; index < times; index += 1) {
    await user.click(screen.getByRole('button', { name: 'Step' }))
  }
}

describe('StoreFloorView', () => {
  it('renders the store floor by default and keeps customers in their own lane', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    await stepTo(user, 3)

    expect(screen.getByLabelText('Store view')).toBeInTheDocument()
    expect(screen.getByTestId('lane-Q1')).toContainElement(screen.getByTestId('customer-2'))
    expect(screen.getByTestId('lane-Q2')).toContainElement(screen.getByTestId('customer-3'))
    expect(screen.getByTestId('lane-Q1')).not.toContainElement(screen.getByTestId('customer-3'))
  })

  it('shows elapsed service time from the traced service_start', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    await stepTo(user, 3)

    // Service started at t=0.1 h, playback is at t=0.3 h -> 12.0 minutes elapsed.
    expect(screen.getByTestId('server-server:Q1')).toHaveTextContent('Service 12.0 min')
  })

  it('renders a lane the run declared but never used', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    await stepTo(user, 3)

    // Q3 produces no trace events at all; it must still appear as a real lane.
    expect(screen.getByTestId('lane-Q3')).toBeInTheDocument()
    expect(screen.getByTestId('server-server:Q3')).toHaveTextContent('Idle')
  })

  it('marks a lane closed only when the caller supplies inactive queues', async () => {
    const user = userEvent.setup()
    const { unmount } = renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    await stepTo(user, 3)
    expect(screen.queryByText('Closed')).not.toBeInTheDocument()
    unmount()

    renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} inactiveQueueIds={['Q3']} />)
    await stepTo(user, 3)
    expect(screen.getByTestId('lane-Q3')).toHaveTextContent('Closed')
    expect(screen.getByTestId('lane-Q1')).not.toHaveTextContent('Closed')
  })

  it('switches back to the diagram view without changing the lane contents', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    await stepTo(user, 3)
    await user.selectOptions(screen.getByLabelText('Floor layout'), 'diagram')

    expect(screen.queryByLabelText('Store view')).not.toBeInTheDocument()
    expect(screen.getByTestId('lane-Q1')).toContainElement(screen.getByTestId('customer-2'))
  })

  it('switches the floor to the dense layout once there are many lanes', () => {
    const { container } = renderWithProviders(
      <SeparateSimulationPlayback trace={makeWideTrace(11)} />,
    )
    expect(container.querySelectorAll('.store-lane')).toHaveLength(11)
    expect(container.querySelector('.store-floor')).toHaveClass('is-dense')
  })

  it('keeps the floor un-dense at the threshold', () => {
    const { container } = renderWithProviders(
      <SeparateSimulationPlayback trace={makeWideTrace(10)} />,
    )
    expect(container.querySelector('.store-floor')).not.toHaveClass('is-dense')
  })

  it('stops animating dots once playback outruns them', async () => {
    const user = userEvent.setup()
    const { container } = renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    expect(container.querySelector('.store-floor')).not.toHaveClass('is-static')

    await user.selectOptions(screen.getByLabelText('Speed'), '5')
    expect(container.querySelector('.store-floor')).toHaveClass('is-static')
  })

  it('offers a 0.25x playback speed', () => {
    renderWithProviders(<SeparateSimulationPlayback trace={makeTrace()} />)
    expect(screen.getByRole('option', { name: '0.25x' })).toBeInTheDocument()
  })
})
