import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { QueueIdEditor } from './QueueIdEditor'

describe('QueueIdEditor', () => {
  it('renders persisted queue IDs as editable inputs', () => {
    const onChange = vi.fn()
    renderWithProviders(<QueueIdEditor ids={['north', 'south']} onChange={onChange} />)
    expect(screen.getByLabelText('Queue ID 1')).toHaveValue('north')
    expect(screen.getByLabelText('Queue ID 2')).toHaveValue('south')
  })

  it('adds an empty row and reports typed names', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { rerender } = renderWithProviders(<QueueIdEditor ids={['north']} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Add queue' }))
    expect(onChange).toHaveBeenLastCalledWith(['north', ''])
    rerender(<QueueIdEditor ids={['north', '']} onChange={onChange} />)
    await user.type(screen.getByLabelText('Queue ID 2'), 'Cashier-A')
    // Controlled input: every keystroke reports the full row set with the latest value.
    expect(onChange).toHaveBeenCalledWith(['north', 'C'])
    expect(onChange).toHaveBeenCalledWith(['north', ''])
  })

  it('removes the selected row without touching the others', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    const { rerender } = renderWithProviders(<QueueIdEditor ids={['north', 'south', 'express']} onChange={onChange} />)
    await user.click(screen.getByRole('button', { name: 'Remove south' }))
    expect(onChange).toHaveBeenLastCalledWith(['north', 'express'])
    rerender(<QueueIdEditor ids={['north', 'express']} onChange={onChange} />)
    expect(screen.queryByDisplayValue('south')).not.toBeInTheDocument()
    expect(screen.getByDisplayValue('express')).toBeInTheDocument()
  })

  it('flags blank values without blocking edits', async () => {
    const user = userEvent.setup()
    const onChange = vi.fn()
    renderWithProviders(<QueueIdEditor ids={['north', '   ']} onChange={onChange} />)
    expect(await screen.findByText('Queue IDs must be non-empty.')).toBeInTheDocument()
    await user.type(screen.getByLabelText('Queue ID 1'), 'X')
    expect(onChange).toHaveBeenCalled()
  })

  it('flags duplicate values after trimming', () => {
    renderWithProviders(<QueueIdEditor ids={['north', ' north ']} onChange={vi.fn()} />)
    expect(screen.getByText('Queue IDs must be unique.')).toBeInTheDocument()
  })

  it('announces the editor region and keeps controls labelled', () => {
    renderWithProviders(<QueueIdEditor ids={[]} onChange={vi.fn()} />)
    expect(screen.getByRole('button', { name: 'Add queue' })).toBeInTheDocument()
    expect(screen.getByText('Configured physical queues')).toBeInTheDocument()
  })
})
