import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders } from '../../test/test-utils'
import { Sidebar } from './Sidebar'

vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({
    user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
  })),
  login: vi.fn(async () => ({})),
  logout: vi.fn(async () => ({})),
}))

describe('Sidebar analysis workflow', () => {
  it('uses the numeric analysis id and presents one ordered workflow', async () => {
    const { container } = renderWithProviders(<Sidebar />, {
      route: '/analyses/7/current',
    })
    expect(await screen.findByText('ANALYSIS WORKFLOW')).toBeInTheDocument()
    const workflowLinks = Array.from(
      container.querySelectorAll<HTMLAnchorElement>('.sidebar-nav a'),
    )
      .map((link) => link.getAttribute('href'))
      .filter((href) => href?.startsWith('/analyses/7/'))
    expect(workflowLinks).toEqual([
      '/analyses/7/setup',
      '/analyses/7/current',
      '/analyses/7/optimize',
      '/analyses/7/compare',
      '/analyses/7/simulate',
      '/analyses/7/decision',
      '/analyses/7/reports',
    ])
    expect(container.querySelector('a[href*="/latest/"]')).not.toBeInTheDocument()
  })
})
