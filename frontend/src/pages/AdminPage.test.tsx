import { describe, it, expect, vi, beforeEach } from 'vitest'
import { screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Route, Routes } from 'react-router-dom'
import { renderWithProviders } from '../test/test-utils'
import { AdminPage } from './AdminPage'
import { RequireRole } from '../auth/RequireRole'

const listUsersMock = vi.fn()
const createUserMock = vi.fn()
const updateUserMock = vi.fn()

vi.mock('../api/users', () => ({
  listUsers: (...args: unknown[]) => listUsersMock(...args),
  createUser: (...args: unknown[]) => createUserMock(...args),
  updateUser: (...args: unknown[]) => updateUserMock(...args),
}))

const meMock = vi.fn()

vi.mock('../api/auth', () => ({
  me: (...args: unknown[]) => meMock(...args),
  login: vi.fn(async () => ({ user: null })),
  logout: vi.fn(async () => ({})),
}))

const users = {
  users: [
    {
      id: 1,
      email: 'a@b.c',
      role: 'admin',
      active: true,
      created_at: '2026-01-01T00:00:00Z',
    },
    {
      id: 2,
      email: 'c@d.e',
      role: 'analyst',
      active: false,
      created_at: '2026-02-01T00:00:00Z',
    },
  ],
}

beforeEach(() => {
  vi.restoreAllMocks()
  listUsersMock.mockReset()
  createUserMock.mockReset()
  updateUserMock.mockReset()
  meMock.mockReset()
  listUsersMock.mockResolvedValue(users)
  createUserMock.mockResolvedValue({ user: { ...users.users[0] } })
  updateUserMock.mockResolvedValue({ user: { ...users.users[0] } })
})

function renderAdmin() {
  return renderWithProviders(
    <Routes>
      <Route path="/admin" element={<RequireRole role="admin" />}>
        <Route index element={<AdminPage />} />
      </Route>
    </Routes>,
    { route: '/admin' },
  )
}

describe('AdminPage', () => {
  it('shows the Forbidden component for a non-admin user', async () => {
    meMock.mockResolvedValue({
      user: { id: 1, email: 'a@b.c', role: 'analyst', active: true, created_at: '2026-01-01T00:00:00Z' },
    })
    renderAdmin()
    expect(await screen.findByText('You do not have permission to view this page.')).toBeInTheDocument()
    expect(listUsersMock).not.toHaveBeenCalled()
  })

  it('renders the users table for an admin', async () => {
    meMock.mockResolvedValue({
      user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
    })
    renderAdmin()
    expect(await screen.findByText('c@d.e')).toBeInTheDocument()
    const table = within(screen.getByRole('table'))
    expect(table.getByText('admin')).toBeInTheDocument()
    expect(table.getByText('analyst')).toBeInTheDocument()
  })

  it('creates a user from the form', async () => {
    const user = userEvent.setup()
    meMock.mockResolvedValue({
      user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
    })
    renderAdmin()
    await screen.findByText('c@d.e')
    await user.type(screen.getByLabelText('Email'), 'new@user.io')
    await user.type(screen.getByLabelText('Password'), 'pw12345')
    await user.click(screen.getByRole('button', { name: 'Create user' }))
    await waitFor(() => {
      expect(createUserMock).toHaveBeenCalledWith(
        { email: 'new@user.io', password: 'pw12345', role: 'analyst' },
        expect.anything(),
      )
    })
  })

  it('deactivates a user after confirmation', async () => {
    const user = userEvent.setup()
    meMock.mockResolvedValue({
      user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
    })
    vi.spyOn(window, 'confirm').mockReturnValue(true)
    renderAdmin()
    await screen.findByText('a@b.c')
    await user.click(screen.getAllByRole('button', { name: 'Deactivate' })[0])
    await waitFor(() => {
      expect(updateUserMock).toHaveBeenCalledWith(1, { active: false })
    })
  })

  it('shows a translated banner when the email already exists', async () => {
    const user = userEvent.setup()
    meMock.mockResolvedValue({
      user: { id: 1, email: 'a@b.c', role: 'admin', active: true, created_at: '2026-01-01T00:00:00Z' },
    })
    createUserMock.mockRejectedValue({
      response: { status: 409, data: { detail: 'Email already registered.' } },
    })
    renderAdmin()
    await screen.findByText('c@d.e')
    await user.type(screen.getByLabelText('Email'), 'dup@user.io')
    await user.type(screen.getByLabelText('Password'), 'pw12345')
    await user.click(screen.getByRole('button', { name: 'Create user' }))
    expect(await screen.findByText('A user with this email already exists.')).toBeInTheDocument()
  })
})
