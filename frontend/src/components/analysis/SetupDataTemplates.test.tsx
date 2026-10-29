import { describe, expect, it, vi, beforeEach } from 'vitest'
import { readFileSync } from 'node:fs'
import { resolve } from 'node:path'
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

  it('marks the field guide table so field names stay on one line', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SetupDataTemplates queueStructure="separate_queues" />)
    await user.click(screen.getByRole('button', { name: 'View Example and Field Guide' }))
    const region = await screen.findByRole('region', { name: 'Field Guide' })
    const table = region.querySelector('table')
    expect(table).toHaveClass('field-guide-table')
    expect(screen.getByRole('rowheader', { name: 'queue_id' }).closest('table')).toBe(table)
    expect(screen.getByRole('region', { name: 'Filled Example' }).querySelector('table'))
      .not.toHaveClass('field-guide-table')
    const css = readFileSync(resolve(process.cwd(), 'src/styles/global.css'), 'utf8')
    expect(css).toMatch(/\.app-shell \.field-guide-table th\[scope='row'\]\s*\{[^}]*overflow-wrap: normal;[^}]*white-space: nowrap;/)
    // On phones the table keeps a readable width and scrolls inside its region instead of squeezing.
    // The selector must outrank `.app-shell .table-scroll table { min-width: 100%; }` (0,2,1).
    expect(css).toMatch(/\.app-shell \.table-scroll table\.field-guide-table\s*\{[^}]*min-width: 40rem;/)
  })

  it('switches between totals and events schemas', async () => {
    const user = userEvent.setup()
    renderWithProviders(<SetupDataTemplates queueStructure="shared_queue" />)
    await user.click(screen.getByRole('button', { name: "Customer Events" }))
    await user.click(screen.getByRole('button', { name: 'View Example and Field Guide' }))
    expect(getTemplateGuideMock).toHaveBeenCalledWith('shared_queue', 'events')
  })
})
