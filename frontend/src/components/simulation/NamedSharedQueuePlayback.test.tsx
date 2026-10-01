import { describe, expect, it } from 'vitest'
import { fireEvent, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { NamedSharedQueuePlayback } from './NamedSharedQueuePlayback'
import type { NamedPlayback } from '../../api/sharedNamed'
import fixture from '../../test/fixtures/sharedNamed.json'

// The fixture is real backend output (scripts/generate_shared_named_fixture.py; synthetic inputs).
const playback = fixture.replication.playback as unknown as NamedPlayback
const START = fixture.request.horizon.start_minute

describe('NamedSharedQueuePlayback', () => {
  it('lists every event once, in seq order, and invents none', () => {
    renderWithProviders(<NamedSharedQueuePlayback playback={playback} horizonStartMinute={START} />)
    const rows = screen.getAllByTestId('named-event-row')
    expect(playback.events.length).toBeLessThanOrEqual(100) // one page holds the whole fixture
    expect(rows).toHaveLength(playback.events.length)
    const seqs = rows.map((row) => Number(within(row).getByRole('rowheader').textContent))
    expect(seqs).toEqual(playback.events.map((event) => event.seq))
    expect(seqs).toEqual([...seqs].sort((a, b) => a - b))
    expect(screen.getByText(`Events 1–${playback.events.length} of ${playback.events.length}`)).toBeInTheDocument()
  })

  it('steps event by event and shows each event with its vocabulary meaning', async () => {
    renderWithProviders(<NamedSharedQueuePlayback playback={playback} horizonStartMinute={START} />)
    const first = playback.events[0]
    const current = () => screen.getByTestId('named-current-event')
    expect(current()).toHaveTextContent(`#${first.seq}`)
    expect(current()).toHaveTextContent('08:00:00')
    await userEvent.click(screen.getByRole('button', { name: 'Step forward' }))
    expect(current()).toHaveTextContent(`#${playback.events[1].seq}`)
    await userEvent.click(screen.getByRole('button', { name: 'Step back' }))
    expect(current()).toHaveTextContent(`#${first.seq}`)
    const closing = playback.events.findIndex((event) => event.type === 'closing')
    fireEvent.change(screen.getByLabelText(/Event \d+ of/), { target: { value: String(closing) } })
    expect(current()).toHaveTextContent(playback.event_vocabulary.customer_trace.closing)
    expect(screen.getByTestId('named-current-period')).toHaveTextContent('Closing')
  })

  it('shows each employee lane with the state and register from the recorded transitions', () => {
    renderWithProviders(<NamedSharedQueuePlayback playback={playback} horizonStartMinute={START} />)
    const lanes = screen.getAllByTestId('named-lane')
    expect(lanes).toHaveLength(Object.keys(playback.employees).length)
    const firstTransition = playback.events.find((event) => event.source === 'employee_transition')
    expect(firstTransition).toBeDefined()
    const lane = lanes.find((item) => item.textContent?.startsWith(firstTransition?.employee_id ?? ''))
    expect(within(lane as HTMLElement).getByTestId('named-lane-state')).toHaveTextContent(firstTransition?.employee_state_after ?? '')
  })

  it('marks closing on every lane and keeps periods visually distinct', () => {
    renderWithProviders(<NamedSharedQueuePlayback playback={playback} horizonStartMinute={START} />)
    expect(screen.getAllByTestId('named-closing-marker')).toHaveLength(Object.keys(playback.employees).length)
    expect(screen.getByText(/Closing at 10:00:00/)).toBeInTheDocument()
    const periods = new Set(playback.events.map((event) => event.period))
    for (const label of ['Operating', 'Closing', 'After closing']) {
      if (periods.has(({ Operating: 'operating_horizon', Closing: 'closing', 'After closing': 'after_closing' } as const)[label as 'Operating'])) {
        expect(screen.getAllByText(label).length).toBeGreaterThan(0)
      }
    }
  })

  it('lists what no event represents separately', () => {
    renderWithProviders(<NamedSharedQueuePlayback playback={playback} horizonStartMinute={START} />)
    const section = screen.getByTestId('named-not-represented')
    expect(section).toHaveTextContent(playback.not_represented_by_events.definition)
    expect(section).toHaveTextContent(`Unfulfilled breaks: ${playback.not_represented_by_events.unfulfilled_breaks.length}`)
    expect(section).toHaveTextContent(`Shifts not activated: ${playback.not_represented_by_events.shifts_not_activated.length}`)
  })

  it('pages a long event log without dropping or adding events', async () => {
    const many = Array.from({ length: 250 }, (_, index) => ({ ...playback.events[0], seq: index }))
    renderWithProviders(<NamedSharedQueuePlayback playback={{ ...playback, events: many }} horizonStartMinute={START} />)
    expect(screen.getAllByTestId('named-event-row')).toHaveLength(100)
    expect(screen.getByText('Events 1–100 of 250')).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText(/Event \d+ of/), { target: { value: '249' } })
    expect(screen.getAllByTestId('named-event-row')).toHaveLength(50)
    expect(screen.getByText('Events 201–250 of 250')).toBeInTheDocument()
  })
})
