import type { ReactElement, ReactNode } from 'react'
import { render } from '@testing-library/react'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { MemoryRouter } from 'react-router-dom'
import { I18nextProvider } from 'react-i18next'
import i18n from 'i18next'
import { initReactI18next } from 'react-i18next'
import { AuthProvider } from '../auth/AuthProvider'
import en from '../../public/locales/en/translation.json'
import tl from '../../public/locales/tl/translation.json'

export function makeQueryClient(): QueryClient {
  return new QueryClient({
    defaultOptions: { queries: { retry: false } },
  })
}

export function testI18n(): typeof i18n {
  if (!i18n.isInitialized) {
    void i18n.use(initReactI18next).init({
      resources: {
        en: { translation: en },
        tl: { translation: tl },
      },
      lng: 'en',
      fallbackLng: 'en',
      interpolation: { escapeValue: false },
    })
  }
  return i18n
}

interface RenderOptions {
  route?: string
  queryClient?: QueryClient
  lang?: 'en' | 'tl'
}

export function renderWithProviders(
  ui: ReactElement,
  { route = '/', queryClient, lang = 'en' }: RenderOptions = {},
) {
  const qc = queryClient ?? makeQueryClient()
  const i18nInstance = testI18n()
  void i18nInstance.changeLanguage(lang)
  function Wrapper({ children }: { children: ReactNode }) {
    return (
      <QueryClientProvider client={qc}>
        <MemoryRouter initialEntries={[route]}>
          <I18nextProvider i18n={i18nInstance}>
            <AuthProvider>{children}</AuthProvider>
          </I18nextProvider>
        </MemoryRouter>
      </QueryClientProvider>
    )
  }
  return { ...render(ui, { wrapper: Wrapper }), queryClient: qc }
}
