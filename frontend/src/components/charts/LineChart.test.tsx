import { describe, expect, it } from 'vitest'
import { act, fireEvent, render, screen } from '@testing-library/react'
import { LineChart, type LineSeries } from './LineChart'

// Phase C (owner decisions 2026-11-25): the line chart draws only what it is given; a null is a gap.

const periods = ['08:00-09:00', '09:00-10:00', '10:00-11:00', '11:00-12:00']

function draw(series: LineSeries[], highlight: number | null = null) {
  return render(
    <LineChart name="Test chart" periods={periods} series={series} max={10} ticks={[0, 5, 10]} formatTick={(value) => String(value)} unit="min"
      readout={(index) => [periods[index], `value ${series[0].values[index] ?? 'Unavailable'}`]}
      liveText={(index) => `${periods[index]}: ${series[0].values[index] ?? 'Unavailable'}`}
      highlight={highlight} revealKey="k" testId="line" />,
  )
}

function pathPoints(path: Element): number {
  return (path.getAttribute('d') ?? '').split(/[ML]/).filter((part) => part.trim() !== '').length
}

describe('LineChart', () => {
  it('splits the line at nulls without drawing a node or a zero for the missing value', () => {
    draw([{ kind: 'rec', values: [2, 4, null, 6] }])
    const chart = screen.getByTestId('line')
    const traces = chart.querySelectorAll('[data-testid="line-trace-rec"]')
    expect([...traces].map(pathPoints)).toEqual([2, 1])
    expect(chart.querySelectorAll('.cv-node-rec')).toHaveLength(3)
    // No point sits on the zero line (y of value 0 is the plot bottom).
    const zeroY = chart.querySelector('.cv-axis-l')?.getAttribute('y1')
    expect([...chart.querySelectorAll('.cv-node-rec')].map((node) => node.getAttribute('cy'))).not.toContain(zeroY)
  })

  it('draws the estimated series as diamonds and marks the highlighted period', () => {
    draw([{ kind: 'est', values: [1, 2, 3, 4] }], 2)
    const nodes = screen.getByTestId('line').querySelectorAll('.cv-node-est')
    expect(nodes).toHaveLength(4)
    expect(nodes[0].tagName.toLowerCase()).toBe('path')
    expect(nodes[2]).toHaveClass('is-highlight')
    expect(screen.getByTestId('line').querySelectorAll('.is-highlight')).toHaveLength(1)
  })

  it('reads out by keyboard (Arrow keys, Home, End) and by hover, with a guide line and a live region', () => {
    draw([{ kind: 'arr', values: [1, null, 3, 4] }])
    const chart = screen.getByRole('group', { name: 'Test chart' })
    expect(chart).toHaveAttribute('aria-roledescription', 'chart')
    expect(chart).toHaveAttribute('tabindex', '0')
    expect(screen.getByTestId('line-chart-readout')).toBeEmptyDOMElement()
    act(() => chart.focus())
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('08:00-09:00value 1')
    expect(screen.getByTestId('line-chart-guide')).toBeInTheDocument()
    fireEvent.keyDown(chart, { key: 'ArrowRight' })
    expect(screen.getByText('09:00-10:00: Unavailable')).toBeInTheDocument()
    fireEvent.keyDown(chart, { key: 'End' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('11:00-12:00value 4')
    fireEvent.keyDown(chart, { key: 'Home' })
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('08:00-09:00value 1')
    fireEvent.mouseEnter(screen.getAllByTestId('line-chart-hit')[2])
    expect(screen.getByTestId('line-chart-readout')).toHaveTextContent('10:00-11:00value 3')
    // Hit areas are pointer targets only, never tab stops.
    expect(screen.getAllByTestId('line-chart-hit').every((hit) => !hit.hasAttribute('tabindex'))).toBe(true)
  })

  it('puts the traces and nodes, and nothing else, in the revealed layer', () => {
    draw([{ kind: 'rec', values: [1, 2, 3, 4] }])
    const layer = screen.getByTestId('line-chart-curves')
    expect(layer).toHaveClass('cv-curve-layer')
    expect(layer.querySelectorAll('.cv-line-grid, .cv-axis-l, .cv-line-hit, text')).toHaveLength(0)
    expect(layer.querySelectorAll('.cv-trace, .cv-node')).toHaveLength(5)
  })
})
