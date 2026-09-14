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

describe('Sidebar global navigation', () => {
  it('keeps workflow navigation out of the global sidebar and provides Help', async () => {
    const { container } = renderWithProviders(<Sidebar />, { route: '/analyses/7/current' })
    expect(await screen.findByText('Help')).toBeInTheDocument()
    const workflowLinks = Array.from(container.querySelectorAll<HTMLAnchorElement>('.sidebar-nav a'))
      .map((link) => link.getAttribute('href'))
      .filter((href) => href?.startsWith('/analyses/7/'))
    expect(workflowLinks).toEqual([])
    expect(container.querySelector('a[href="/help"]')).toBeInTheDocument()
    expect(screen.queryByText('ANALYSIS WORKFLOW')).not.toBeInTheDocument()
    expect(container.querySelector('a[href*="/latest/"]')).not.toBeInTheDocument()
  })
})
