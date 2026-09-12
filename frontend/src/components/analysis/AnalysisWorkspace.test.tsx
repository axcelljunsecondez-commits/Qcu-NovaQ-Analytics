import { useState } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { fireEvent, render, screen } from '@testing-library/react'
import { I18nextProvider } from 'react-i18next'
import { createMemoryRouter, RouterProvider } from 'react-router-dom'
import { beforeEach, describe, expect, it, vi } from 'vitest'
import { makeQueryClient, testI18n } from '../../test/test-utils'
import { AnalysisWorkspace } from './AnalysisWorkspace'

const getMock = vi.fn()
const listMock = vi.fn()

vi.mock('../../api/analyses', () => ({
  getAnalysis: (...args: unknown[]) => getMock(...args),
  listAnalyses: (...args: unknown[]) => listMock(...args),
}))

function item(id: number) {
  return {
    id,
    name: `Analysis ${id}`,
    service_type: null,
    location_label: null,
    queue_setup: {
      queue_structure: 'shared_queue',
      fixed_server_count: 2,
      staffing_varies_by_period: false,
      capacity_mode: 'unlimited',
      total_system_capacity: null,
      abandonment_mode: 'not_modeled',
      patience_rate_per_hour: null,
    },
    setup_status: 'ready',
    archived_at: null,
    created_at: '2026-09-08T00:00:00Z',
    updated_at: '2026-09-08T00:00:00Z',
  }
}

function TransientProbe() {
  const [count, setCount] = useState(0)
  return <button type="button" onClick={() => setCount((value) => value + 1)}>Transient {count}</button>
}

beforeEach(() => {
  getMock.mockReset()
  listMock.mockReset()
  getMock.mockImplementation(async (id: number) => ({ analysis: item(id) }))
  listMock.mockResolvedValue({ analyses: [item(1), item(2)] })
})

describe('AnalysisWorkspace', () => {
  it('uses the route as context and resets transient child state when switching', async () => {
    const router = createMemoryRouter(
      [{
        path: '/analyses/:analysisId',
        element: <AnalysisWorkspace />,
        children: [{ path: 'current', element: <TransientProbe /> }],
      }],
      { initialEntries: ['/analyses/1/current'] },
    )
    render(
      <QueryClientProvider client={makeQueryClient()}>
        <I18nextProvider i18n={testI18n()}>
          <RouterProvider router={router} />
        </I18nextProvider>
      </QueryClientProvider>,
    )
    expect(await screen.findByRole('heading', { name: 'Analysis 1' })).toBeInTheDocument()
    expect(screen.getByText('Step 2 of 7')).toBeInTheDocument()
    expect(screen.getByRole('link', { name: 'Back: Setup' })).toHaveAttribute(
      'href',
      '/analyses/1/setup',
    )
    expect(screen.getByRole('link', { name: 'Next: Optimize' })).toHaveAttribute(
      'href',
      '/analyses/1/optimize',
    )
    fireEvent.click(screen.getByRole('button', { name: 'Transient 0' }))
    expect(screen.getByRole('button', { name: 'Transient 1' })).toBeInTheDocument()
    fireEvent.change(screen.getByLabelText('Switch Analysis'), { target: { value: '2' } })
    expect(await screen.findByRole('heading', { name: 'Analysis 2' })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Transient 0' })).toBeInTheDocument()
    expect(router.state.location.pathname).toBe('/analyses/2/current')
  })
})
