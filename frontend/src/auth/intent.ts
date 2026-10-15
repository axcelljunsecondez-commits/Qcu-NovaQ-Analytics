// Where to go after signing in (spec 2026-10-09 §7.2).
// Intent comes from RequireAuth (`location.state.from`), from `?next=` on Home's
// Start button, or from sessionStorage across the registration and email-verification
// round trip. Every source is untrusted and passes safeNext before use.

export const INTENT_KEY = 'novaq_intent'
export const DEFAULT_AFTER_SIGN_IN = '/analyses'

const AUTH_ROUTES = ['/login', '/register', '/verify-email', '/forgot-password', '/reset-password']
const CHECK_ORIGIN = 'https://novaq.invalid'

// Returns a same-origin app path (path, query and hash), or null when the value
// could leave the app (`//host`, `/\host`, absolute URLs) or points at an auth page.
export function safeNext(value: unknown): string | null {
  if (typeof value !== 'string' || !value.startsWith('/') || value.startsWith('//') || value.startsWith('/\\')) return null
  if (Array.from(value).some((char) => char.charCodeAt(0) < 0x20 || char.charCodeAt(0) === 0x7f)) return null
  let url: URL
  try {
    url = new URL(value, CHECK_ORIGIN)
  } catch {
    return null
  }
  if (url.origin !== CHECK_ORIGIN) return null
  const path = url.pathname.replace(/\/+$/, '') || '/'
  if (AUTH_ROUTES.some((route) => path === route || path.startsWith(`${route}/`))) return null
  return `${url.pathname}${url.search}${url.hash}`
}

export function rememberIntent(value: unknown): void {
  const next = safeNext(value)
  if (!next) return
  try {
    sessionStorage.setItem(INTENT_KEY, next)
  } catch {
    // Convenience only: without storage the user lands on My analyses.
  }
}

function takeStoredIntent(): string | null {
  try {
    const stored = sessionStorage.getItem(INTENT_KEY)
    sessionStorage.removeItem(INTENT_KEY)
    return stored
  } catch {
    return null
  }
}

// The first safe candidate wins; the stored intent is consumed either way.
export function continueAfterSignIn(...candidates: unknown[]): string {
  const stored = takeStoredIntent()
  for (const candidate of [...candidates, stored]) {
    const next = safeNext(candidate)
    if (next) return next
  }
  return DEFAULT_AFTER_SIGN_IN
}

// Read without consuming, for links that keep the intent (Sign in ↔ Create account).
export function pendingIntent(...candidates: unknown[]): string | null {
  for (const candidate of candidates) {
    const next = safeNext(candidate)
    if (next) return next
  }
  try {
    return safeNext(sessionStorage.getItem(INTENT_KEY))
  } catch {
    return null
  }
}
