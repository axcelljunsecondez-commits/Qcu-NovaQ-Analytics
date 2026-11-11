import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { ResultsSummary } from './ResultsSummary'
import type { PeriodArrivals } from '../../api/types'
import type { ResultRow } from '../../lib/results'

const rows = [
  { time: '08:00-09:00', queue_id: 'Lane A', c: 1, Wq: 0.25, rho: 0.85, stable: true },
  { time: '09:00-10:00', queue_id: 'Lane B', c: null, Wq: null, rho: 1.2, stable: false },
]
function summary(period = '__all__', line = '__all__', source: ResultRow[] = rows, arrivalsByPeriod: PeriodArrivals[] = [], arrivalRecords?: Record<string, unknown>[]) {
  const onPeriod = vi.fn()
  const onLine = vi.fn()
  renderWithProviders(<ResultsSummary rows={source} arrivalsByPeriod={arrivalsByPeriod} arrivalRecords={arrivalRecords} period={period} line={line} onPeriod={onPeriod} onLine={onLine} referenceLink={<a href="?view=reference">Inputs and model</a>} />)
  return { onPeriod, onLine }
}

describe('operational summary', () => {
  it('presents the most severe cashier lines first with the original wait values', () => {
    summary('__all__', '__all__', rows, [{ time: rows[0].time, arrivals_per_hour: 40 }])
    expect(screen.queryByRole('list', { name: 'Busiest periods with arrival data' })).not.toBeInTheDocument()
    const table = screen.getByRole('table')
    expect(within(table).getAllByRole('columnheader').map((cell) => cell.textContent)).toEqual(['Period', "Service Line", "Current Open Counter", 'Estimated wait (min)', 'Busy level'])
    const waitCells = within(table).getAllByRole('cell').filter((cell) => cell.textContent === '15 min')
    expect(waitCells).toHaveLength(1)
    expect(waitCells[0]).toBeVisible()
    expect(waitCells[0].textContent).toBe('15 min')
    expect(within(table).getByText("Can't keep up · 120%")).toBeInTheDocument()
    expect(within(table).getByText('Unavailable')).toBeInTheDocument()
    const list = screen.getByRole('list', { name: 'Current operation by period' })
    const cards = within(list).getAllByRole('listitem')
    expect(cards).toHaveLength(2)
    expect(cards[0]).toHaveTextContent('Lane B')
    expect(cards[0]).toHaveTextContent("Can't keep up")
    expect(cards[1]).toHaveTextContent('Lane A')
    expect(cards[1]).toHaveTextContent('15 min')
    expect(within(cards[0]).getAllByRole('term')).toHaveLength(5)
  })

  it('filters the same rows and delegates filter changes without changing the values', async () => {
    const user = userEvent.setup()
    const { onPeriod, onLine } = summary('08:00-09:00', 'Lane A')
    expect(within(screen.getByRole('table')).queryByText('Lane B')).not.toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Current operation by period' })).queryByText('Lane B')).not.toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText('Time'), '09:00-10:00')
    await user.selectOptions(screen.getByLabelText("Service Line"), 'Lane B')
    expect(onPeriod).toHaveBeenCalledWith('09:00-10:00')
    expect(onLine).toHaveBeenCalledWith('Lane B')
  })

  it('shows the five highest known arrival rates when no workload row qualifies', () => {
    const periods = [8, 22, null, 34, 6, 19, 15, 27].map((rate, i) => ({ time: 'Period ' + (i + 1), arrivals_per_hour: rate }))
    summary('__all__', '__all__', [{ ...rows[0], rho: 0.8 }], periods)
    const arrivals = screen.getByRole('list', { name: 'Busiest periods with arrival data' })
    expect(within(arrivals).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      'Period 4 · 34 customers per hour',
      'Period 8 · 27 customers per hour',
      'Period 2 · 22 customers per hour',
      'Period 6 · 19 customers per hour',
      'Period 7 · 15 customers per hour',
    ])
    expect(screen.queryByText('Showing 0 of 0')).not.toBeInTheDocument()
    expect(screen.getByText('No available workload estimates exceeded 80%.')).toBeInTheDocument()
  })

  it('shows arrival data for a period without a workload estimate', () => {
    summary('10:00-11:00', '__all__', rows, [{ time: '10:00-11:00', arrivals_per_hour: 22 }])
    expect(screen.getByText('Workload estimates are incomplete for this selection.')).toBeInTheDocument()
    expect(within(screen.getByRole('list', { name: 'Busiest periods with arrival data' })).getByText(/22 customers per hour/)).toBeInTheDocument()
  })

  it('uses the selected cashier line and period for the arrivals fallback', () => {
    const lines = [
      { ...rows[0], rho: 0.7, lambda: 2 },
      { ...rows[0], time: '09:00-10:00', rho: 0.72, lambda: 9 },
      { ...rows[1], time: '08:00-09:00', rho: 0.75, lambda: 25, stable: true },
    ]
    const input = [
      { time: '08:00-09:00', queue_id: 'Lane A', lambda: 12 },
      { time: '09:00-10:00', queue_id: 'Lane A', lambda: 9 },
      { time: '08:00-09:00', queue_id: 'Lane B', lambda: 25 },
    ]
    summary('08:00-09:00', 'Lane A', lines, [{ time: '08:00-09:00', arrivals_per_hour: 37 }], input)
    const arrivals = screen.getByRole('list', { name: 'Busiest periods with arrival data' })
    expect(within(arrivals).getAllByRole('listitem').map((item) => item.textContent)).toEqual([
      '08:00-09:00 · 12 customers per hour',
    ])
  })

  it('leaves out an ambiguous arrival rate for a selected cashier and period', () => {
    const input = [
      { time: '08:00-09:00', queue_id: 'Lane A', lambda: 12 },
      { time: '08:00-09:00', queue_id: 'Lane A', lambda: 5 },
    ]
    summary('__all__', 'Lane A', [{ ...rows[0], rho: 0.7, lambda: 17 }], [], input)
    expect(screen.queryByRole('list', { name: 'Busiest periods with arrival data' })).not.toBeInTheDocument()
  })

  it('distinguishes a normal workload from a missing estimate', () => {
    const clean = { ...rows[0], rho: 0.7 }
    const { unmount } = renderWithProviders(<ResultsSummary rows={[clean]} period="__all__" line="__all__"
      onPeriod={vi.fn()} onLine={vi.fn()} referenceLink={null} />)
    expect(screen.getByText('No available workload estimates exceeded 80%.')).toBeInTheDocument()
    unmount()
    summary('__all__', '__all__', [{ ...clean, rho: Number.NaN }])
    expect(screen.getByText('Workload estimates are incomplete for this selection.')).toBeInTheDocument()
  })
})
