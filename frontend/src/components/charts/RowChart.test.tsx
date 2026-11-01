import { afterEach, describe, expect, it, vi } from 'vitest'
import { act, fireEvent, render, screen, within } from '@testing-library/react'
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
  it('gives every selectable row a 44px hit area in its own row strip', () => {
    renderChart()
    const targets = screen.getAllByTestId('row-chart-row').map((row) => row.querySelector('rect')!)
    for (const target of targets) expect(Number(target.getAttribute('height'))).toBeGreaterThanOrEqual(44)
    expect(new Set(targets.map((target) => target.closest('svg'))).size).toBe(rows.length)
    for (const target of targets) expect(Number(target.closest('svg')?.getAttribute('height'))).toBe(46)
  })

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

describe('RowChart label column', () => {
  // jsdom has no SVG text layout, so the measured label length is stubbed. In the browser a per-date
  // label ("2000-01-03 05:00-06:00 UTC") measured 161 px and ran under the marks of an 82 px column.
  function axisStart(container: HTMLElement): number {
    const row = container.querySelector<HTMLElement>('.cv-row-grid')!
    return Number.parseFloat(row.style.gridTemplateColumns) + Number(row.querySelector('.cv-axis-l')?.getAttribute('x1'))
  }
  function stubTextLength(length: number) {
    const proto = window.SVGElement.prototype as unknown as { getComputedTextLength?: () => number }
    const before = proto.getComputedTextLength
    proto.getComputedTextLength = () => length
    return () => { if (before) proto.getComputedTextLength = before; else delete proto.getComputedTextLength }
  }

  it('keeps the base column when the labels fit', () => {
    const restore = stubTextLength(60)
    const { container } = render(<RowChart name="c" rows={rows} max={2} ticks={[0, 1, 2]} formatTick={String} />)
    expect(axisStart(container)).toBe(104)
    restore()
  })

  it('widens the column to the longest label so the axis starts after it', () => {
    const restore = stubTextLength(161)
    const { container } = render(<RowChart name="c" rows={rows} max={2} ticks={[0, 1, 2]} formatTick={String} />)
    expect(axisStart(container)).toBe(161 + 4 + 14)
    restore()
  })

  it('moves an uncapped label above a full-width plot when inline columns cannot fit', () => {
    const restore = stubTextLength(500)
    const { container } = render(<RowChart name="c" rows={rows} max={2} ticks={[0, 1, 2]} formatTick={String} />)
    expect(screen.getByRole('group', { name: 'c' })).toHaveAttribute('data-layout', 'compact')
    const plot = container.querySelector('.cv-row-plot')!
    expect(Number(plot.getAttribute('width'))).toBe(600)
    expect(container.querySelector('.cv-row-label')).toHaveTextContent(rows[0].label)
    restore()
  })
})

describe('RowChart responsive text and plot geometry', () => {
  const label = '2026-09-08 SYNTHETIC Morning checkout operations 08-to-09 UTC'
  const side = 'SYNTHETIC Cashier Benjamin - Household essentials checkout'
  const sublabel = 'Two observation dates with recorded service durations'
  const longRows = rows.map((row, index) => ({ ...row, label: `${label} ${index}`, sublabel, sideLabel: side }))
  const restorers: Array<() => void> = []

  afterEach(() => {
    restorers.splice(0).forEach((restore) => restore())
    vi.restoreAllMocks()
    vi.unstubAllGlobals()
  })

  function measurements(width: number, left = 448, right = 625) {
    const current = { width }
    vi.spyOn(HTMLElement.prototype, 'clientWidth', 'get').mockImplementation(() => current.width)
    const proto = window.SVGElement.prototype as unknown as { getComputedTextLength?: () => number }
    const before = proto.getComputedTextLength
    proto.getComputedTextLength = function (this: SVGElement) { return this.textContent === side ? right : left }
    restorers.push(() => { if (before) proto.getComputedTextLength = before; else delete proto.getComputedTextLength })
    return current
  }

  function plotGeometry(container: HTMLElement) {
    const plot = container.querySelector<SVGSVGElement>('.cv-row-plot')!
    const start = Number(plot.querySelector('.cv-axis-l')!.getAttribute('x1'))
    return { plot, start, width: Number(plot.getAttribute('width')) }
  }

  it.each([290, 684, 1196])('preserves full labels and right-side names with at least 180px axis span at %ipx', (chartWidth) => {
    measurements(chartWidth)
    const { container } = render(<RowChart name="compact" rows={longRows} max={2} ticks={[0, 1, 2]} formatTick={String} sideWidth={128} />)
    const chart = screen.getByRole('group', { name: 'compact' })
    expect(chart).toHaveAttribute('data-layout', 'compact')
    const { plot, start, width } = plotGeometry(container)
    expect(width - 2 * start).toBeGreaterThanOrEqual(180)
    expect(width + 12).toBeLessThan(chartWidth)
    expect(plot.closest<HTMLElement>('.cv-row-grid')!.style.gridTemplateColumns).toBe(`${width}px minmax(0, 1fr)`)
    for (const [index, row] of screen.getAllByTestId('row-chart-row').entries()) {
      expect(row.querySelector('.cv-row-title')!.textContent).toBe(longRows[index].label)
      expect(row.querySelector('.cv-row-sublabel')!.textContent).toBe(sublabel)
      expect(row.querySelector('.cv-row-side')!.textContent).toBe(side)
      expect(row.lastElementChild).toHaveClass('cv-row-side')
      expect(row.querySelector('rect')).toHaveAttribute('height', '44')
    }
    expect(container.querySelector('.cv-chart-measure')!.childNodes).toHaveLength(0)
  })

  it('uses identical x mapping for marks, ranges, grid, cut markers and the common reference', () => {
    measurements(290)
    const { container } = render(<RowChart name="geometry" rows={longRows} max={2} ticks={[0, 1, 2]} formatTick={String}
      reference={{ value: 1.5, label: 'cap' }} />)
    const plots = Array.from(container.querySelectorAll('.cv-row-plot'))
    const { width, start } = plotGeometry(container)
    const x = (value: number) => start + value / 2 * (width - 2 * start)
    expect(plots[0].querySelector('.cv-m-est')).toHaveAttribute('cx', String(x(1)))
    expect(plots[0].querySelector('.cv-m-rec')).toHaveAttribute('d', expect.stringContaining(`M${x(2)} `))
    expect(plots[1].querySelector('.cv-m-plan')).toHaveAttribute('cx', String(x(0.5)))
    expect(plots[1].querySelector('.cv-l-ci')).toHaveAttribute('x1', String(x(0)))
    expect(plots[1].querySelector('.cv-l-ci')).toHaveAttribute('x2', String(x(1.5)))
    expect(plots[1].querySelector('.cv-m-clip')).toHaveAttribute('d', expect.stringContaining(`M${start - 1} `))
    for (const reference of container.querySelectorAll('.cv-l-cap')) expect(reference).toHaveAttribute('x1', String(x(1.5)))
    for (const plot of plots) expect(plot.querySelector('.cv-grid-l')).toHaveAttribute('x1', String(x(1)))
  })

  it('gives plots the full compact width when there is no right-side label', () => {
    measurements(290)
    const { container } = render(<RowChart name="no side" rows={longRows.map((row) => ({ ...row, sideLabel: undefined }))}
      max={2} ticks={[0, 1, 2]} formatTick={String} sideWidth={128} />)
    expect(screen.getByRole('group', { name: 'no side' })).toHaveAttribute('data-layout', 'compact')
    expect(plotGeometry(container).width).toBe(290)
    expect(container.querySelector('.cv-row-side')).not.toBeInTheDocument()
  })

  it('preserves zero and maximum clamping in compact strips', () => {
    measurements(290)
    const bounded: ChartRow[] = [{ ...longRows[0], marks: [{ kind: 'est', value: -1 }, { kind: 'plan', value: 8 }], connect: [-1, 8] }]
    const { container } = render(<RowChart name="bounds" rows={bounded} max={2} ticks={[0, 1, 2]} formatTick={String} />)
    const { plot, start, width } = plotGeometry(container)
    expect(plot.querySelector('.cv-m-est')).toHaveAttribute('cx', String(start))
    expect(plot.querySelector('.cv-m-plan')).toHaveAttribute('cx', String(width - start))
    expect(plot.querySelector('.cv-l-gap')).toHaveAttribute('x1', String(start))
    expect(plot.querySelector('.cv-l-gap')).toHaveAttribute('x2', String(width - start))
  })

  it('measures the uncapped right label and keeps that measurement across renderer resizing', () => {
    const current = measurements(600, 60, 625)
    let resize = () => {}
    vi.stubGlobal('ResizeObserver', class {
      constructor(callback: () => void) { resize = callback }
      observe() {}
      disconnect() {}
    })
    render(<RowChart name="resize" rows={longRows} max={2} ticks={[0, 1, 2]} formatTick={String} />)
    const chart = screen.getByRole('group', { name: 'resize' })
    expect(chart).toHaveAttribute('data-layout', 'compact')
    act(() => { current.width = 1200; resize() })
    expect(chart).toHaveAttribute('data-layout', 'wide')
    act(() => { current.width = 290; resize() })
    expect(chart).toHaveAttribute('data-layout', 'compact')
    act(() => { current.width = 1200; resize() })
    expect(chart).toHaveAttribute('data-layout', 'wide')
  })

  it('keeps compact row selection, keyboard navigation and readout independent of wrapping', async () => {
    measurements(290)
    const select = vi.fn()
    const user = userEvent.setup()
    render(<RowChart name="select compact" rows={longRows} max={2} ticks={[0, 1, 2]} formatTick={String} initialRow={1} onSelect={select} />)
    fireEvent.click(screen.getAllByTestId('row-chart-row')[2])
    expect(select).toHaveBeenLastCalledWith(2)
    expect(screen.getAllByTestId('row-chart-row')[2]).toHaveClass('active')
    await user.keyboard('{Home}{ArrowDown}{Enter}')
    expect(select).toHaveBeenLastCalledWith(1)
    expect(screen.getByTestId('row-chart-readout')).toHaveTextContent(rows[1].readout[0])
    expect(screen.getByText(rows[1].liveText)).toBeInTheDocument()
  })
})
