import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen } from '@testing-library/react'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { RequireRole } from './RequireRole'

const meMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(async () => ({ user: null })),
  logout: vi.fn(async () => ({})),
}))

beforeEach(() => {
  vi.restoreAllMocks()
  meMock.mockReset()
})

function renderRoute(role: 'admin' | 'analyst') {
  meMock.mockResolvedValue({
    user: { id: 1, email: 'a@b.c', role, active: true, created_at: '2026-01-01T00:00:00Z' },
  })
  return renderWithProviders(
    <Routes>
      <Route path="/admin" element={<RequireRole role="admin" />}>
        <Route index element={<div>admin-page-marker</div>} />
      </Route>
    </Routes>,
    { route: '/admin' },
  )
}

describe('RequireRole', () => {
  it('renders Forbidden when a non-admin navigates to /admin', async () => {
    renderRoute('analyst')
    expect(await screen.findByText('You do not have permission to view this page.')).toBeInTheDocument()
    expect(screen.queryByText('admin-page-marker')).not.toBeInTheDocument()
  })

  it('renders the page when an admin navigates to /admin', async () => {
    renderRoute('admin')
    expect(await screen.findByText('admin-page-marker')).toBeInTheDocument()
  })
})
