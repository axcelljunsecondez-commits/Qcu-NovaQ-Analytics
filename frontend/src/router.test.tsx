import { describe, expect, it } from 'vitest'
import { createAppRouter } from './router'

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
