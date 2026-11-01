import { afterEach, describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import type { LongestMatrix } from '../../lib/longestLine'
import { renderWithProviders } from '../../test/test-utils'
import en from '../../../public/locales/en/translation.json'
import { LongestLineTable } from './LongestLineTable'

// Longest Single Line table (spec 2026-10-29 §7.4, owner decision B6).

const matrix: LongestMatrix = {
  lanes: ['cashier_1', 'cashier_2', 'cashier_3'],
  rows: [
    { time: '05:00-06:00', max: 1, cells: [
      { lane: 'cashier_1', staffed: true, value: 1, rho: 0.0019 },
      { lane: 'cashier_2', staffed: true, value: null, rho: null },
      { lane: 'cashier_3', staffed: false, value: null, rho: null },
    ] },
    { time: '06:00-07:00', max: 4, cells: [
      { lane: 'cashier_1', staffed: true, value: 0, rho: 0 },
      { lane: 'cashier_2', staffed: true, value: 4, rho: 0.8661645 },
      { lane: 'cashier_3', staffed: true, value: 2, rho: 0.5 },
    ] },
  ],
  dayMax: 4,
  peaks: [{ time: '06:00-07:00', lane: 'cashier_2' }],
  staffingKnown: true,
}

const width = window.innerWidth

function setWidth(value: number) {
  Object.defineProperty(window, 'innerWidth', { configurable: true, writable: true, value })
  window.dispatchEvent(new Event('resize'))
}

afterEach(() => setWidth(width))

function renderTable(kind: 'current' | 'plan' = 'current', data: LongestMatrix = matrix) {
  return renderWithProviders(<LongestLineTable matrix={data} kind={kind} chips={['Current', 'One period at a time', en['charts.chip_seed_not_saved']]} />)
}

describe('LongestLineTable', () => {
  it('prints the stored values, keeps a missing value Unavailable and gives hatched cells a text alternative', () => {
    renderTable()
    const first = screen.getByRole('row', { name: /^05:00-06:00/ })
    const cells = within(first).getAllByRole('cell')
    expect(cells.map((cell) => cell.textContent)).toEqual(['1', 'Unavailable', `—${en['simulation.state_closed']}`, 'Unavailable'])
    expect(cells[2]).toHaveClass('cv-closed')
    expect(within(cells[2]).getByText(en['simulation.state_closed'])).toHaveClass('sr-only')
    // A staffed zero is printed as 0, not hatched.
    expect(within(screen.getByRole('row', { name: /^06:00-07:00/ })).getAllByRole('cell')[0]).toHaveTextContent('0')
    expect(screen.queryByTestId('longest-take')).not.toBeInTheDocument()
  })

  it('states a whole-run maximum only when every staffed cell is known', () => {
    const complete = { ...matrix, rows: matrix.rows.map((period) => ({ ...period,
      cells: period.cells.map((cell) => cell.staffed === true && cell.value === null ? { ...cell, value: 0 } : cell),
    })) }
    renderTable('current', complete)
    expect(screen.getByTestId('longest-take')).toHaveTextContent('Longest line in today’s simulated run: 4 people, at cashier_2 during 06:00-07:00.')
    const cells = within(screen.getByRole('row', { name: /^05:00-06:00/ })).getAllByRole('cell')
    expect(cells[3]).toHaveTextContent('1')
  })

  it('shows an unknown-staffing cell as "—" without hatching and leaves the hatching key out', () => {
    const unknown: LongestMatrix = {
      ...matrix, staffingKnown: false,
      rows: [{ time: '05:00-06:00', max: 1, cells: [
        { lane: 'cashier_1', staffed: true, value: 1, rho: 0.5 },
        { lane: 'cashier_2', staffed: null, value: null, rho: null },
        { lane: 'cashier_3', staffed: true, value: 0, rho: 0 },
      ] }],
      dayMax: 1, peaks: [{ time: '05:00-06:00', lane: 'cashier_1' }],
    }
    renderTable('current', unknown)
    const cells = within(screen.getByRole('row', { name: /^05:00-06:00/ })).getAllByRole('cell')
    expect(cells[1]).toHaveTextContent('—')
    expect(cells[1]).not.toHaveClass('cv-closed')
    expect(within(cells[1]).getByText('Unavailable')).toHaveClass('sr-only')
    const table = screen.getByTestId('longest-line-table')
    expect(table.querySelector('.cv-closed')).toBeNull()
    expect(within(table).queryByText(en['simulation.state_closed'])).not.toBeInTheDocument()
    expect(screen.queryByTestId('longest-take')).not.toBeInTheDocument()
    expect(cells[3]).toHaveTextContent('Unavailable')
  })

  it('keeps the hatching key when staffing is known', () => {
    renderTable()
    expect(within(screen.getByTestId('longest-line-table')).getAllByText(en['simulation.state_closed'])[0].closest('li')).not.toBeNull()
  })

  it('uses the singular takeaway and the plan wording for the plan run', () => {
    const completePeriod = { ...matrix.rows[0], cells: matrix.rows[0].cells.map((cell) => cell.staffed === true && cell.value === null ? { ...cell, value: 0 } : cell) }
    renderTable('plan', { ...matrix, rows: [completePeriod], dayMax: 1, peaks: [{ time: '05:00-06:00', lane: 'cashier_1' }] })
    expect(screen.getByTestId('longest-take')).toHaveTextContent('Longest line in the plan’s simulated day: 1 person, at cashier_1 during 05:00-06:00.')
  })

  it('has no takeaway when no cell has a value', () => {
    renderTable('current', { ...matrix, dayMax: null, peaks: [] })
    expect(screen.queryByTestId('longest-take')).not.toBeInTheDocument()
  })

  it('names the cashiers in the header on a wide screen', () => {
    setWidth(1280)
    renderTable()
    const headers = screen.getAllByRole('columnheader').map((header) => header.textContent)
    expect(headers).toEqual(['Time', 'cashier_1', 'cashier_2', 'cashier_3', 'Longest Single Line'])
    expect(screen.queryByTestId('longest-columns')).not.toBeInTheDocument()
  })

  it('reads 1…n with a key line at 520 px or less', () => {
    setWidth(375)
    renderTable()
    const headers = screen.getAllByRole('columnheader')
    expect(headers.map((header) => header.textContent)).toEqual(['Time', '1', '2', '3', '↑'])
    expect(headers[1]).toHaveAccessibleName('cashier_1')
    expect(headers[4]).toHaveAccessibleName('Longest Single Line')
    expect(screen.getByTestId('longest-columns')).toHaveTextContent('Columns 1–3 = cashier_1 … cashier_3')
  })

  it('moves between cells with the arrow keys and reads the focused cell out', async () => {
    const user = userEvent.setup()
    renderTable()
    const cells = screen.getAllByRole('cell')
    expect(cells.filter((cell) => cell.tabIndex === 0)).toHaveLength(1)
    await user.click(cells[0])
    expect(cells[0]).toHaveFocus()
    expect(screen.getByTestId('longest-readout')).toHaveTextContent('05:00-06:00 · cashier_1Most waiting at once: 1Workload: 0.19%')
    await user.keyboard('{ArrowRight}{ArrowRight}')
    expect(screen.getByTestId('longest-readout')).toHaveTextContent(`05:00-06:00 · cashier_3${en['simulation.state_closed']}`)
    await user.keyboard('{ArrowDown}')
    expect(screen.getByTestId('longest-readout')).toHaveTextContent('06:00-07:00 · cashier_3')
    await user.keyboard('{End}')
    expect(screen.getByTestId('longest-readout')).toHaveTextContent('06:00-07:00Longest Single Line: 4')
    expect(screen.getByText('06:00-07:00, Longest Single Line: 4')).toHaveAttribute('aria-live', 'polite')
    await user.keyboard('{Home}{ArrowLeft}{ArrowUp}{ArrowUp}')
    expect(screen.getByTestId('longest-readout')).toHaveTextContent('05:00-06:00 · cashier_1')
  })
})
