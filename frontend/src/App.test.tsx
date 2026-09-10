import { describe, it, expect } from 'vitest'
import { screen } from '@testing-library/react'
import { renderWithProviders, testI18n } from './test/test-utils'

describe('test infrastructure', () => {
  it('provides i18n resources for en and tl', () => {
    const i18nInstance = testI18n()
    expect(i18nInstance.t('login.submit')).toBe('Sign in')
    void i18nInstance.changeLanguage('tl')
    expect(i18nInstance.t('login.submit')).toBe('Mag-sign in')
  })

  it('renderWithProviders renders children with providers', () => {
    renderWithProviders(<div>NovaQ</div>)
    expect(screen.getByText('NovaQ')).toBeInTheDocument()
  })
})
