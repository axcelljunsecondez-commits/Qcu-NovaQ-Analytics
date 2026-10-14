import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { continueAfterSignIn, INTENT_KEY, pendingIntent, rememberIntent, safeNext } from './intent'

beforeEach(() => sessionStorage.clear())
afterEach(() => vi.restoreAllMocks())

describe('safeNext (spec §7.2)', () => {
  it.each([
    ['/analyses/new', '/analyses/new'],
    ['/analyses/7/simulate?mode=named#replay', '/analyses/7/simulate?mode=named#replay'],
    ['/settings/files', '/settings/files'],
    ['/', '/'],
  ])('accepts the app path %s', (value, expected) => {
    expect(safeNext(value)).toBe(expected)
  })

  it.each([
    ['protocol-relative', '//evil.example/path'],
    ['backslash host', '/\\evil.example'],
    ['absolute https', 'https://evil.example/analyses'],
    ['javascript scheme', 'javascript:alert(1)'],
    ['relative path', 'analyses/new'],
    ['empty', ''],
    ['sign-in page', '/login'],
    ['sign-in page with query', '/login?next=/analyses'],
    ['registration', '/register'],
    ['email verification', '/verify-email'],
    ['forgot password', '/forgot-password'],
    ['password reset', '/reset-password/'],
    ['control character', '/analyses\n/new'],
    ['tab trick', '/\t/evil.example'],
    ['not a string', 42],
    ['null', null],
  ])('rejects %s', (_label, value) => {
    expect(safeNext(value)).toBeNull()
  })
})

describe('continueAfterSignIn', () => {
  it('uses the first safe candidate', () => {
    expect(continueAfterSignIn('//evil.example', '/analyses/new')).toBe('/analyses/new')
    expect(continueAfterSignIn('/tools/calculator', '/analyses/new')).toBe('/tools/calculator')
  })

  it('falls back to My analyses', () => {
    expect(continueAfterSignIn(undefined, null, 'https://evil.example')).toBe('/analyses')
  })

  it('uses and then forgets the intent kept during registration', () => {
    rememberIntent('/analyses/new')
    expect(sessionStorage.getItem(INTENT_KEY)).toBe('/analyses/new')
    expect(pendingIntent()).toBe('/analyses/new')
    expect(continueAfterSignIn(undefined, null)).toBe('/analyses/new')
    expect(sessionStorage.getItem(INTENT_KEY)).toBeNull()
    expect(continueAfterSignIn(undefined, null)).toBe('/analyses')
  })

  it('never stores an unsafe intent and ignores one planted in storage', () => {
    rememberIntent('//evil.example')
    expect(sessionStorage.getItem(INTENT_KEY)).toBeNull()
    sessionStorage.setItem(INTENT_KEY, 'https://evil.example')
    expect(continueAfterSignIn()).toBe('/analyses')
  })

  it('works when session storage is blocked', () => {
    vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => {
      throw new Error('blocked')
    })
    expect(() => rememberIntent('/analyses/new')).not.toThrow()
    expect(continueAfterSignIn(undefined, '/analyses/new')).toBe('/analyses/new')
    expect(continueAfterSignIn()).toBe('/analyses')
    expect(pendingIntent()).toBeNull()
  })
})
