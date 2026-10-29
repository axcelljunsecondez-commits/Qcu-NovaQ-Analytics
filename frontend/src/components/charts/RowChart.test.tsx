import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { RowChart, type ChartRow } from './RowChart'

const rows: ChartRow[] = [
  { key: 'a', label: '08:00-09:00', marks: [{ kind: 'est', value: 1 }, { kind: 'rec', value: 2 }], connect: [1, 2], readout: ['08:00-09:00', 'Estimated: 1 min'], liveText: '08:00-09:00: Estimated 1 min' },
  { key: 'b', label: '09:00-10:00', marks: [{ kind: 'plan', value: 0.5 }], range: { low: 0, high: 1.5, cut: true }, highlight: true, readout: ['09:00-10:00'], liveText: '09:00-10:00: plan 0.5 min' },
  { key: 'c', label: '10:00-11:00', marks: [], gapLabel: 'Unavailable', readout: ['10:00-11:00', 'Unavailable'], liveText: '10:00-11:00: Unavailable' },
]

function renderChart(onSelect = vi.fn()) {
  render(<RowChart name="Wait by hour" rows={rows} max={2} ticks={[0, 1, 2]} formatTick={String} unit="min" initialRow={1} onSelect={onSelect}
    reference={{ value: 1.5, label: 'cap' }} />)
  return onSelect
}

describe('RowChart', () => {
  it('is one named, focusable chart group with the drawn rows, a labelled gap, a cut marker and a reference line', () => {
    renderChart()
    const chart = screen.getByRole('group', { name: 'Wait by hour' })
    expect(chart).toHaveAttribute('tabindex', '0')
    expect(screen.getAllByTestId('row-chart-row')).toHaveLength(3)
    expect(screen.getAllByTestId('row-chart-cut')).toHaveLength(1)
    expect(within(chart).getByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('row-chart-reference')).toHaveTextContent('cap')
    expect(screen.getAllByTestId('row-chart-row')[1]).toHaveClass('hl')
  })

  it('starts at the initial row on focus and moves with Arrow, Home and End keys', async () => {
    const user = userEvent.setup()
    renderChart()
    await user.tab()
    expect(screen.getByText('09:00-10:00: plan 0.5 min')).toBeInTheDocument()
    await user.keyboard('{ArrowDown}')
    expect(screen.getByText('10:00-11:00: Unavailable')).toBeInTheDocument()
    expect(screen.getByTestId('row-chart-readout')).toHaveTextContent('10:00-11:00Unavailable')
    await user.keyboard('{Home}')
    expect(screen.getByText('08:00-09:00: Estimated 1 min')).toBeInTheDocument()
    await user.keyboard('{ArrowUp}')
    expect(screen.getByText('08:00-09:00: Estimated 1 min')).toBeInTheDocument()
    await user.keyboard('{End}')
    expect(screen.getByText('10:00-11:00: Unavailable')).toBeInTheDocument()
  })

  it('selects a row on Enter and on click', async () => {
    const user = userEvent.setup()
    const onSelect = renderChart()
    await user.tab()
    await user.keyboard('{Enter}')
    expect(onSelect).toHaveBeenLastCalledWith(1)
    fireEvent.click(screen.getAllByTestId('row-chart-row')[0])
    expect(onSelect).toHaveBeenLastCalledWith(0)
    expect(screen.getAllByTestId('row-chart-row')[0]).toHaveClass('active')
  })
})
