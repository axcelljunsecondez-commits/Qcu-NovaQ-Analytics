import en from '../../../public/locales/en/translation.json'
import { describe, expect, it, vi } from 'vitest'
import { screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { renderWithProviders } from '../../test/test-utils'
import { LanguageSelector } from './LanguageSelector'
import { initializeTheme } from '../../lib/theme'
import { HomePage } from '../../pages/HomePage'
import { PublicShell } from './PublicShell'

vi.mock('../../api/auth', () => ({
  me: vi.fn(async () => ({ user: null })),
  login: vi.fn(),
  logout: vi.fn(),
}))

describe('layout preferences', () => {
  it('migrates a saved dark preference before rendering the light interface', () => {
    localStorage.setItem('novaq_theme', 'dark')
    document.documentElement.dataset.theme = 'dark'
    initializeTheme()
    expect(document.documentElement.dataset.theme).toBe('light')
    expect(document.documentElement.style.colorScheme).toBe('light')
    expect(localStorage.getItem('novaq_theme')).toBe('light')
  })

  it('still initializes light when device storage is blocked', () => {
    const write = vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
    document.documentElement.dataset.theme = 'dark'
    expect(() => initializeTheme()).not.toThrow()
    expect(document.documentElement.dataset.theme).toBe('light')
    write.mockRestore()
  })

  it.each([['Home', HomePage], ['Public frame', PublicShell]] as const)('keeps %s language/navigation with no retired theme control', async (_name, Page) => {
    renderWithProviders(<Page />)
    await screen.findByRole('navigation', { name: en['home.header_navigation'] })
    expect(screen.queryByRole('button', { name: /Dark Mode|Light Mode/ })).not.toBeInTheDocument()
    expect(screen.getByRole('combobox', { name: /Language/i })).toBeInTheDocument()
  })

  it('uses text language controls and keeps document language synchronized', async () => {
    const user = userEvent.setup()
    renderWithProviders(<LanguageSelector />)
    expect(screen.getByRole('button', { name: 'English' })).toHaveTextContent('EN English')
    await user.click(screen.getByRole('button', { name: 'Filipino' }))
    expect(document.documentElement.lang).toBe('tl')
  })
})
