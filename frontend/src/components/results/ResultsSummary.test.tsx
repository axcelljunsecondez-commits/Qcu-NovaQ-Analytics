import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { ResultsSummary } from './ResultsSummary'

const rows = [
  { time: '08:00-09:00', queue_id: 'Lane A', c: 1, Wq: 0.25, rho: 0.75, stable: true },
  { time: '09:00-10:00', queue_id: 'Lane B', c: null, Wq: null, rho: 1.2, stable: false },
]
function summary(period = '__all__', line = '__all__', source = rows) {
  const onPeriod = vi.fn()
  const onLine = vi.fn()
  renderWithProviders(<ResultsSummary rows={source} period={period} line={line} onPeriod={onPeriod} onLine={onLine} planTarget={0.7} referenceLink={<a href="?view=reference">Inputs and model</a>} />)
  return { onPeriod, onLine }
}

describe('operational summary', () => {
  it('retains every field and overloaded/missing meaning in both presentations', () => {
    summary()
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Period', 'Service line', 'Counters open', 'Estimated wait (min)', 'Busy level'])
    expect(within(table).getByText('15 min')).toBeInTheDocument()
    expect(within(table).getByText("Can't keep up")).toBeInTheDocument()
    expect(within(table).getByText('Unavailable')).toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Current operation by period' })
    const cards = within(list).getAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(cards[0]).toHaveTextContent('Lane A')
    expect(cards[0]).toHaveTextContent('15 min')
    expect(cards[1]).toHaveTextContent('Lane B')
    expect(cards[1]).toHaveTextContent("Can't keep up")
    expect(within(cards[0]).getAllByRole('term')).toHaveLength(5)
  })

  it('filters the same rows and delegates filter changes without changing the values', async () => {
    const user = userEvent.setup()
    const { onPeriod, onLine } = summary('08:00-09:00', 'Lane A')
    expect(within(screen.getByRole('table')).queryByText('Lane B')).not.toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Current operation by period' })).queryByText('Lane B')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Time'), '09:00-10:00')
    await user.selectOptions(screen.getByLabelText('Service line'), 'Lane B')
    expect(onPeriod).toHaveBeenCalledWith('09:00-10:00')
    expect(onLine).toHaveBeenCalledWith('Lane B')
  })

  it('preserves the target warning when only one period makes the strip redundant', () => {
    summary('__all__', '__all__', [rows[0]])
    expect(screen.getByRole('status')).toHaveTextContent("above this plan's target of 70%")
  })
})
