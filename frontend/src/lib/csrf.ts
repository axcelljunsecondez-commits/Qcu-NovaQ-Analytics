export const SESSION_COOKIE = 'novamart_session'
export const CSRF_COOKIE = 'novamart_csrf'

function cookieValue(name: string): string | null {
  return (
    document.cookie
      .split('; ')
      .find((c) => c.startsWith(`${name}=`))
      ?.split('=')[1] ?? null
  )
}

export function getCsrfToken(): string | null {
  return cookieValue(CSRF_COOKIE)
}
