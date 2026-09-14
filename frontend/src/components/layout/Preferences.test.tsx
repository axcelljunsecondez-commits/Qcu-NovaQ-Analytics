import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { LanguageSelector } from './LanguageSelector'
import { ThemeToggle } from './ThemeToggle'

vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

describe('layout preferences', () => {
  it('updates visible theme state and persists it', async () => {
    localStorage.setItem('novaq_theme', 'light')
    document.documentElement.dataset.theme = 'light'
    const user = userEvent.setup()
    renderWithProviders(<ThemeToggle />)
    const toggle = screen.getByRole('button', { name: 'Dark Mode' })
    expect(toggle).toHaveAttribute('aria-pressed', 'false')
    await user.click(toggle)
    expect(screen.getByRole('button', { name: 'Light Mode' })).toHaveAttribute('aria-pressed', 'true')
    expect(document.documentElement.dataset.theme).toBe('dark')
    expect(localStorage.getItem('novaq_theme')).toBe('dark')
  })

  it('uses text language controls and keeps document language synchronized', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LanguageSelector />)
    expect(screen.getByRole('button', { name: 'English' })).toHaveTextContent('EN English')
    await user.click(screen.getByRole('button', { name: 'Filipino' }))
    expect(document.documentElement.lang).toBe('tl')
  })
})
