import { describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { AnalysisSelector } from './AnalysisSelector'

describe('controlled analysis selector', () => {
  it('exposes the complete selected identity and delegates a change without choosing a default', async () => {
    const user = userEvent.setup()
    const change = vi.fn()
    const name = 'A very long source-owned analysis name that must remain readable beside the native selector'
    renderWithProviders(<AnalysisSelector id="test-analysis" label="Analysis" value="7" options={[{ id: 7, name }, { id: 9, name: 'Second' }]} onChange={change} />)
    const select = screen.getByRole('combobox', { name: 'Analysis' })
    expect(select).toHaveValue('7')
    expect(select).toHaveAccessibleDescription(name)
    expect(within(select).getAllByRole('option')).toHaveLength(2)
    expect(change).not.toHaveBeenCalled()
    await user.selectOptions(select, '9')
    expect(change).toHaveBeenCalledExactlyOnceWith('9')
    expect(select).toHaveValue('7') // caller remains the state owner
  })
})
