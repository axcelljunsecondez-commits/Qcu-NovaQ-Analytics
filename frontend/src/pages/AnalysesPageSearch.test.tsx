import { beforeEach, describe, expect, it, vi } from 'vitest'
import { screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes, useLocation } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { AnalysesPage } from './AnalysesPage'

const listMock = vi.fn()
const archiveMock = vi.fn()
vi.mock('../api/analyses', () => ({
  listAnalyses: (...args: unknown[]) => listMock(...args),
  archiveAnalysis: (...args: unknown[]) => archiveMock(...args),
}))
vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

function project(id: number, name: string, extra: Record<string, unknown> = {}, setup: Record<string, unknown> = {}) {
  return {
    id,
    name,
    service_type: null,
    location_label: null,
    queue_setup: { queue_structure: 'shared_queue', segments: [], ...setup },
    setup_status: 'ready',
    archived_at: null,
    created_at: '2026-10-01T00:00:00Z',
    updated_at: '2026-10-01T00:00:00Z',
    ...extra,
  }
}

const analyses = [
  project(1, 'North checkout', { location_label: 'Quezon City' }),
  project(2, 'Pharmacy counters', { service_type: 'Pharmacy' }, {
    queue_structure: 'separate_queues',
    segments: [
      { id: 'b', start_time: '12:00:00', end_time: '18:00:00', active_queue_ids: null },
      { id: 'a', start_time: '08:00:00', end_time: '12:00:00', active_queue_ids: null },
    ],
  }),
  project(3, 'Bank lobby'),
]

function Where() {
  const location = useLocation()
  return <p data-testid="where">{location.pathname}{location.search}</p>
}

function renderAt(route: string) {
  return renderWithProviders(
    <Routes><Route path="/analyses" element={<><AnalysesPage /><Where /></>} /></Routes>,
    { route },
  )
}

beforeEach(() => {
  listMock.mockReset().mockResolvedValue({ analyses })
  archiveMock.mockReset().mockResolvedValue({ analysis: analyses[0] })
})

function names() {
  return screen.queryAllByRole('heading', { level: 2 }).map((heading) => heading.textContent)
}

describe('My analyses search (spec §7.4)', () => {
  it('searches name, location and service type and keeps the search in the URL', async () => {
    const user = userEvent.setup()
    renderAt('/analyses')
    const search = await screen.findByLabelText('Search analyses')
    expect(screen.getByText('3 analyses')).toBeInTheDocument()
    await user.type(search, 'quezon')
    expect(names()).toEqual(['North checkout'])
    expect(screen.getByTestId('where')).toHaveTextContent('/analyses?q=quezon')
    await user.clear(search)
    await user.type(search, 'PHARM')
    expect(names()).toEqual(['Pharmacy counters'])
    expect(screen.getByText('1 analysis')).toBeInTheDocument()
    await user.clear(search)
    expect(names()).toHaveLength(3)
    expect(screen.getByTestId('where')).toHaveTextContent(/^\/analyses$/)
  })

  it('restores search and structure filter from the URL', async () => {
    renderAt('/analyses?q=counter&structure=separate_queues')
    expect(await screen.findByLabelText('Search analyses')).toHaveValue('counter')
    expect(names()).toEqual(['Pharmacy counters'])
    expect(screen.getByRole('button', { name: 'Separate lines' })).toHaveAttribute('aria-pressed', 'true')
  })

  it('combines search with the structure filter and explains an empty result', async () => {
    renderAt('/analyses?q=bank&structure=separate_queues')
    expect(await screen.findByText('No analyses match this filter.')).toBeInTheDocument()
    expect(screen.getByText('0 analyses')).toBeInTheDocument()
  })

  it('shows the operating window only when time segments are saved', async () => {
    renderAt('/analyses')
    const pharmacy = (await screen.findByRole('heading', { name: 'Pharmacy counters' })).closest('article') as HTMLElement
    expect(within(pharmacy).getByText('Operating window 08:00–18:00')).toBeInTheDocument()
    const north = screen.getByRole('heading', { name: 'North checkout' }).closest('article') as HTMLElement
    expect(within(north).queryByText(/Operating window/)).not.toBeInTheDocument()
    expect(within(north).getByText('Everyone waits in one line')).toBeInTheDocument()
    expect(within(pharmacy).getByText('Each counter has its own line')).toBeInTheDocument()
  })
})

describe('Archive confirmation (spec §7.4, §10)', () => {
  it('asks first, focuses Cancel, and cancels with Escape without archiving', async () => {
    const user = userEvent.setup()
    renderAt('/analyses')
    const card = (await screen.findByRole('heading', { name: 'Bank lobby' })).closest('article') as HTMLElement
    const archiveButton = within(card).getByRole('button', { name: 'Archive' })
    await user.click(archiveButton)
    const dialog = screen.getByRole('alertdialog', { name: 'Archive \u201cBank lobby\u201d?' })
    expect(dialog).toHaveAttribute('aria-modal', 'true')
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
    await user.keyboard('{Escape}')
    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(archiveButton).toHaveFocus()
    expect(archiveMock).not.toHaveBeenCalled()
  })

  it('keeps keyboard focus inside the dialog', async () => {
    const user = userEvent.setup()
    renderAt('/analyses')
    await user.click(within((await screen.findByRole('heading', { name: 'Bank lobby' })).closest('article') as HTMLElement).getByRole('button', { name: 'Archive' }))
    const dialog = screen.getByRole('alertdialog')
    await user.tab()
    expect(within(dialog).getByRole('button', { name: 'Archive' })).toHaveFocus()
    await user.tab()
    expect(within(dialog).getByRole('button', { name: 'Cancel' })).toHaveFocus()
    await user.tab({ shift: true })
    expect(within(dialog).getByRole('button', { name: 'Archive' })).toHaveFocus()
  })

  it('archives the chosen analysis after confirming and moves focus to search', async () => {
    const user = userEvent.setup()
    renderAt('/analyses')
    await user.click(within((await screen.findByRole('heading', { name: 'Bank lobby' })).closest('article') as HTMLElement).getByRole('button', { name: 'Archive' }))
    await user.click(within(screen.getByRole('alertdialog')).getByRole('button', { name: 'Archive' }))
    expect(archiveMock.mock.calls[0][0]).toBe(3)
    expect(screen.getByLabelText('Search analyses')).toHaveFocus()
  })
})
