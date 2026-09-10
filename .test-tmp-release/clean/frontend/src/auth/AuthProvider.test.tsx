import { act, fireEvent, render, screen, waitFor } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { describe, expect, it, vi } from 'vitest'
import { AuthProvider } from './AuthProvider'
import { useAuth } from './useAuth'

vi.mock('../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(async () => ({ user: { id: 1, email: 'admin@example.com', role: 'admin', active: true } })),
  logout: vi.fn(async () => ({})),
}))

function Probe() {
  const { user, login, logout } = useAuth()
  return <><span data-testid="session">{user?.role ?? 'signed out'}</span>
    <button onClick={() => void login('admin@example.com', 'pw')}>login</button>
    <button onClick={() => void logout()}>logout</button></>
}

describe('authoritative session state', () => {
  it.each(['expired', 'deactivated', 'role changed', 'logout'])('supersedes login after %s', async (transition) => {
    const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    render(<QueryClientProvider client={client}><AuthProvider><Probe /></AuthProvider></QueryClientProvider>)
    await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent('signed out'))
    fireEvent.click(screen.getByText('login'))
    await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent('admin'))
    if (transition === 'logout') fireEvent.click(screen.getByText('logout'))
    else act(() => { client.setQueryData(['me'], transition === 'role changed' ? { id: 1, role: 'analyst' } : null) })
    await waitFor(() => expect(screen.getByTestId('session')).toHaveTextContent(transition === 'role changed' ? 'analyst' : 'signed out'))
  })
})
