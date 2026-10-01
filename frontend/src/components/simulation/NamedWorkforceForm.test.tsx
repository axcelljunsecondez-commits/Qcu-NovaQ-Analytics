import { useState } from 'react'
import { describe, expect, it } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { NamedWorkforceForm } from './NamedWorkforceForm'
import type { NamedContract } from '../../api/sharedNamed'
import type { DatasetOut } from '../../api/types'
import { emptyForm, type NamedForm } from '../../lib/namedWorkforce'
import fixture from '../../test/fixtures/sharedNamed.json'

const contract = fixture.contract as unknown as NamedContract
const datasets = [
  { id: 4, analysis_id: 1, name: 'Processed', source_filename: 'a.csv', source_format: 'csv', row_count: 2, validation: { ok: true }, created_at: '', normalized: null },
  { id: 5, analysis_id: 1, name: 'Broken', source_filename: 'b.csv', source_format: 'csv', row_count: 2, validation: { ok: false }, created_at: '', normalized: null },
] as unknown as DatasetOut[]

let latest: NamedForm = emptyForm()

function Harness() {
  const [form, setForm] = useState<NamedForm>(emptyForm)
  latest = form
  return <NamedWorkforceForm form={form} onChange={setForm} contract={contract} datasets={datasets} />
}

describe('NamedWorkforceForm', () => {
  it('starts with no defaults', () => {
    renderWithProviders(<Harness />)
    expect(latest).toEqual(emptyForm())
    expect(screen.getByLabelText('Dataset')).toHaveValue('')
    expect(screen.queryAllByTestId('named-segment-row')).toHaveLength(0)
    for (const radio of within(screen.getByRole('radiogroup')).getAllByRole('radio')) expect(radio).not.toBeChecked()
    expect(screen.getByLabelText('Opening')).toHaveValue('')
  })

  it('lists only successfully processed datasets', () => {
    renderWithProviders(<Harness />)
    const options = within(screen.getByLabelText('Dataset')).getAllByRole('option').map((option) => option.textContent)
    expect(options).toEqual(['Select a dataset', '#4 — Processed'])
  })

  it('has no name field: employees are pseudonymous ids', async () => {
    renderWithProviders(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Add employee' }))
    expect(screen.getByLabelText('Employee ID (pseudonymous)')).toBeInTheDocument()
    expect(screen.getByText('Do not enter real names.')).toBeInTheDocument()
    expect(screen.queryByLabelText(/^name$/i)).toBeNull()
    expect(screen.queryByLabelText(/full name|first name|last name/i)).toBeNull()
  })

  it('keeps pay explicitly not supplied until the user enters a value', async () => {
    renderWithProviders(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Add employee' }))
    const rate = screen.getByLabelText('Regular rate per hour')
    expect(rate).toBeDisabled()
    expect(latest.employees[0].pay.regular_rate_per_hour).toEqual({ value: '', not_supplied: true })
    await userEvent.click(screen.getAllByLabelText('Not supplied')[0])
    await userEvent.type(screen.getByLabelText('Regular rate per hour'), '95.5')
    expect(latest.employees[0].pay.regular_rate_per_hour).toEqual({ value: '95.5', not_supplied: false })
  })

  it('shows the approved employee policy read-only from the contract', () => {
    renderWithProviders(<Harness />)
    const panel = screen.getByTestId('named-employee-policy')
    for (const [name, item] of Object.entries(contract.employee_policy)) {
      expect(panel).toHaveTextContent(name)
      expect(panel).toHaveTextContent(item.approved)
      expect(panel).toHaveTextContent(item.meaning)
    }
    expect(within(panel).queryAllByRole('textbox')).toHaveLength(0)
    expect(within(panel).queryAllByRole('combobox')).toHaveLength(0)
  })

  it('enables the gap between shifts only when more than one shift is allowed', async () => {
    renderWithProviders(<Harness />)
    const gap = screen.getByLabelText('Minimum minutes between shifts')
    expect(gap).toBeDisabled()
    await userEvent.type(screen.getByLabelText('Maximum shifts per employee'), '2')
    expect(screen.getByLabelText('Minimum minutes between shifts')).toBeEnabled()
  })

  it('adds required-staffing segments only by the user', async () => {
    renderWithProviders(<Harness />)
    await userEvent.click(screen.getByRole('button', { name: 'Add segment' }))
    expect(latest.required_staffing).toEqual([{ segment_id: '', start: '', end: '', servers: '' }])
    expect(screen.queryByRole('button', { name: /copy|optimi[sz]e|from dataset|from roster/i })).toBeNull()
  })
})
