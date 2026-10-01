import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { NamedAttributionTables } from './NamedAttributionTables'
import type { NamedAttribution } from '../../api/sharedNamed'
import fixture from '../../test/fixtures/sharedNamed.json'
import { fmtDecimal } from '../../lib/format'

const attribution = fixture.replication.attribution as unknown as NamedAttribution

describe('NamedAttributionTables', () => {
  it('renders one row per shift and per employee, in hours', () => {
    renderWithProviders(<NamedAttributionTables attribution={attribution} />)
    const shiftRows = screen.getAllByTestId('named-attr-shift-row')
    const employeeRows = screen.getAllByTestId('named-attr-employee-row')
    expect(shiftRows).toHaveLength(attribution.shifts.length)
    expect(employeeRows).toHaveLength(attribution.employees.length)
    attribution.shifts.forEach((shift, index) => {
      const row = within(shiftRows[index])
      expect(row.getByRole('rowheader')).toHaveTextContent(shift.employee_id)
      expect(row.getAllByText(fmtDecimal(shift.on_duty_hours)).length).toBeGreaterThan(0)
    })
    expect(screen.getByText('All durations are in hours.')).toBeInTheDocument()
  })

  it('shows the closing cells for each shift', () => {
    renderWithProviders(<NamedAttributionTables attribution={attribution} />)
    const shift = attribution.shifts[0]
    const row = within(screen.getAllByTestId('named-attr-shift-row')[0])
    const cells = row.getAllByRole('cell').map((cell) => cell.textContent)
    expect(cells.slice(-4)).toEqual([
      fmtDecimal(shift.closing_attribution.after_closing_hours),
      fmtDecimal(shift.closing_attribution.past_scheduled_end_hours),
      fmtDecimal(shift.closing_attribution.after_closing_and_past_scheduled_end_hours),
      fmtDecimal(shift.closing_attribution.neither_hours),
    ])
  })

  it('states that this is operational attribution, not performance evaluation, and shows no money', () => {
    renderWithProviders(<NamedAttributionTables attribution={attribution} />)
    expect(screen.getByRole('note')).toHaveTextContent('not employee performance scoring')
    // The tables carry no money; the domain's own "not_reported" definition may name what is excluded.
    for (const table of screen.getAllByRole('table')) {
      expect(table.textContent).not.toMatch(/cost|wage|salary|pay|₱|\$/i)
    }
  })
})
