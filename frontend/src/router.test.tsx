import { act, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import type { InternalAxiosRequestConfig } from 'axios'
import { I18nextProvider } from 'react-i18next'
import { RouterProvider } from 'react-router-dom'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { createAppRouter } from './router'
import { http, isClientUpdateRequired, resetClientUpdateForTests } from './lib/http'
import { testI18n } from './test/test-utils'

interface RouteLike {
  path?: string
  children?: RouteLike[]
}

function routePaths(routes: RouteLike[], parent = ''): string[] {
  return routes.flatMap((route) => {
    const current = route.path
      ? route.path.startsWith('/')
        ? route.path
        : parent
          ? `${parent.replace(/\/$/, '')}/${route.path}`
          : route.path
      : parent
    return [
      ...(route.path ? [current] : []),
      ...routePaths(route.children ?? [], current),
    ]
  })
}

describe('canonical route contract', () => {
  it('defines every current global and analysis deep link', () => {
    const paths = routePaths(createAppRouter().routes as RouteLike[])
    expect(paths).toEqual(expect.arrayContaining([
      '/login',
      '/register',
      '/verify-email',
      '/forgot-password',
      '/reset-password',
      '/onboarding',
      '/help',
      '/dashboard',
      '/analyses',
      '/analyses/new',
      '/analyses/:analysisId/setup',
      '/analyses/:analysisId/guided-setup',
      '/analyses/:analysisId/current',
      '/analyses/:analysisId/optimize',
      '/analyses/:analysisId/compare',
      '/analyses/:analysisId/simulate',
      '/analyses/:analysisId/decision',
      '/analyses/:analysisId/reports',
      '/datasets',
      '/analysis',
      '/account',
      '/admin',
      '*',
    ]))
    expect(paths).not.toEqual(expect.arrayContaining(['/optimize', '/simulate', '/compare']))
  })
})

describe('client update screen', () => {
  const originalAdapter = http.defaults.adapter

  beforeEach(() => {
    resetClientUpdateForTests()
    window.history.pushState({}, '', '/login')
    http.defaults.adapter = (async (config: InternalAxiosRequestConfig) => ({
      data: config.url === '/auth/me' ? { user: null } : { google_sign_in_enabled: false },
      status: 200,
      statusText: 'OK',
      headers: {},
      config,
    })) as typeof http.defaults.adapter
  })

  afterEach(() => {
    http.defaults.adapter = originalAdapter
    resetClientUpdateForTests()
  })

  it('blocks the mounted application, clears its query cache, and offers a document reload', async () => {
    const reloadDocument = vi.fn()
    const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
    queryClient.setQueryData(['scenarios', 7], { scenarios: [{ id: 1 }] })
    const router = createAppRouter(reloadDocument)
    const { container } = render(
      <QueryClientProvider client={queryClient}>
        <I18nextProvider i18n={testI18n()}>
          <RouterProvider router={router} />
        </I18nextProvider>
      </QueryClientProvider>,
    )
    await waitFor(() => expect(container.querySelector('.login-page')).not.toBeNull())

    await act(async () => {
      await expect(http.get('/trigger', {
        adapter: async () => Promise.reject({ response: { status: 403, data: { code: 'client_update_required' } } }),
      })).rejects.toThrow('Reload the application')
    })

    expect(isClientUpdateRequired()).toBe(true)
    expect(queryClient.getQueryData(['scenarios', 7])).toBeUndefined()
    expect(container.querySelector('.login-page')).toBeNull()
    expect(screen.getByRole('alert')).toHaveTextContent('NovaQ has been updated.')
    await userEvent.setup().click(screen.getByRole('button', { name: 'Reload application' }))
    expect(reloadDocument).toHaveBeenCalledOnce()
    router.dispose()
    queryClient.clear()
  })
})
