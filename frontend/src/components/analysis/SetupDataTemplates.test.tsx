import { describe, expect, it, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { SetupDataTemplates } from './SetupDataTemplates'

const getTemplateGuideMock = vi.fn()
const downloadTemplateMock = vi.fn()

vi.mock('../../api/templates', () => ({
  getTemplateGuide: (...args: unknown[]) => getTemplateGuideMock(...args),
  downloadTemplate: (...args: unknown[]) => downloadTemplateMock(...args),
}))

const guide = {
  structure: 'separate_queues',
  schema: 'aggregate',
  columns: ['time', 'queue_id', 'lambda', 'mu', 'c', 'variance'],
  example_rows: [
    { time: '08:00-09:00', queue_id: 'queue_1', lambda: 10, mu: 12, c: 1, variance: 0.006 },
  ],
  field_guide: [
    { field: 'queue_id', meaning: 'Which waiting line the row belongs to.', required: 'Required for separate queues', example: 'queue_1', notes: '' },
    { field: 'lambda', meaning: 'Average arrivals per hour.', required: 'Required', example: '30', notes: '' },
  ],
  accepted_aliases: {},
}

beforeEach(() => {
  getTemplateGuideMock.mockReset().mockResolvedValue(guide)
  downloadTemplateMock.mockReset().mockResolvedValue(undefined)
})

describe('SetupDataTemplates', () => {
  it('renders nothing until the queue structure is confirmed', () => {
    const { container } = renderWithProviders(<SetupDataTemplates queueStructure="unknown" />)
    expect(container).toBeEmptyDOMElement()
    expect(getTemplateGuideMock).not.toHaveBeenCalled()
  })

  it('shows separate-queue template downloads and guide with queue identity', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SetupDataTemplates queueStructure="separate_queues" />)
    expect(screen.getByRole('button', { name: 'Download CSV Template' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Download XLSX Template' })).toBeInTheDocument()
    await user.click(screen.getByRole('button', { name: 'View Example and Field Guide' }))
    await screen.findByText('Which waiting line the row belongs to.')
    expect(screen.getAllByText('queue_id').length).toBeGreaterThan(0)
    await user.click(screen.getByRole('button', { name: 'Download CSV Template' }))
    expect(downloadTemplateMock).toHaveBeenCalledWith('separate_queues', 'aggregate', 'csv')
  })

  it('switches between totals and events schemas', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SetupDataTemplates queueStructure="shared_queue" />)
    await user.click(screen.getByRole('button', { name: 'Customer events' }))
    await user.click(screen.getByRole('button', { name: 'View Example and Field Guide' }))
    expect(getTemplateGuideMock).toHaveBeenCalledWith('shared_queue', 'events')
  })
})
