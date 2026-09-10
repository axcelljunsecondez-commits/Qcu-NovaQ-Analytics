export function takeFragmentToken(name = 'token'): string | null {
  const fragment = window.location.hash.startsWith('#') ? window.location.hash.slice(1) : ''
  const token = new URLSearchParams(fragment).get(name)
  if (window.location.hash) {
    window.history.replaceState(window.history.state, '', `${window.location.pathname}${window.location.search}`)
  }
  return token
}

export function apiErrorCode(error: unknown): string | undefined {
  return (error as { response?: { data?: { code?: string } } }).response?.data?.code
}
