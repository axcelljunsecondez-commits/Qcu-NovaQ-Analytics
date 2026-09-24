// Cloudflare Pages Function: same-origin bridge from /api/* to the NovaQ API.
// Mirrors nginx/nginx.conf and the Vite dev proxy: strip the leading /api and
// forward to NOVAQ_API_ORIGIN, keeping cookies and the CSRF header intact.

export interface ApiProxyEnv {
  NOVAQ_API_ORIGIN?: string
}

interface PagesContext {
  request: Request
  env: ApiProxyEnv
}

// Only headers the API actually needs; proxy, hop-by-hop and cf-* headers are dropped.
const FORWARDED_REQUEST_HEADERS = [
  'accept',
  'accept-language',
  'content-type',
  'cookie',
  'if-modified-since',
  'if-none-match',
  'origin',
  'user-agent',
  'x-csrf-token',
  'x-request-id',
]

const DROPPED_RESPONSE_HEADERS = [
  'connection',
  'keep-alive',
  'proxy-authenticate',
  'proxy-connection',
  'set-cookie',
  'te',
  'trailer',
  'transfer-encoding',
  'upgrade',
]

const LOCAL_HOSTS = new Set(['localhost', '127.0.0.1'])

function jsonError(status: number, code: string, detail: string): Response {
  return new Response(JSON.stringify({ code, detail }), {
    status,
    headers: { 'Content-Type': 'application/json', 'Cache-Control': 'no-store' },
  })
}

/** Exact HTTPS origin (plain HTTP only for localhost), or null when misconfigured. */
export function parseApiOrigin(raw: string | undefined): string | null {
  if (!raw) return null
  let url: URL
  try {
    url = new URL(raw.trim())
  } catch {
    return null
  }
  const secure = url.protocol === 'https:' || (url.protocol === 'http:' && LOCAL_HOSTS.has(url.hostname))
  const bare = (url.pathname === '/' || url.pathname === '') && !url.search && !url.hash && !url.username && !url.password
  return secure && bare ? url.origin : null
}

/** /api -> /, /api/auth/config -> /auth/config; null for anything outside /api. */
export function stripApiPrefix(pathname: string): string | null {
  if (pathname === '/api') return '/'
  if (pathname.startsWith('/api/')) return pathname.slice('/api'.length)
  return null
}

function getSetCookies(headers: Headers): string[] {
  if (typeof headers.getSetCookie === 'function') return headers.getSetCookie()
  const legacy = headers as Headers & { getAll?: (name: string) => string[] }
  if (typeof legacy.getAll === 'function') return legacy.getAll('Set-Cookie')
  const single = headers.get('set-cookie')
  return single ? [single] : []
}

export async function proxyApiRequest(request: Request, env: ApiProxyEnv): Promise<Response> {
  const apiOrigin = parseApiOrigin(env.NOVAQ_API_ORIGIN)
  if (!apiOrigin) return jsonError(500, 'api_origin_unconfigured', 'The API origin is not configured.')

  const incoming = new URL(request.url)
  const path = stripApiPrefix(incoming.pathname)
  if (path === null) return jsonError(404, 'not_found', 'Not found.')

  const headers = new Headers()
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name)
    if (value !== null) headers.set(name, value)
  }

  const hasBody = request.method !== 'GET' && request.method !== 'HEAD'
  let upstream: Response
  try {
    upstream = await fetch(apiOrigin + path + incoming.search, {
      method: request.method,
      headers,
      body: hasBody ? await request.arrayBuffer() : undefined,
      redirect: 'manual',
    })
  } catch {
    return jsonError(502, 'api_unreachable', 'The API could not be reached. Try again shortly.')
  }

  const responseHeaders = new Headers(upstream.headers)
  for (const name of DROPPED_RESPONSE_HEADERS) responseHeaders.delete(name)
  // Each cookie must stay its own Set-Cookie header (session, CSRF, nonce clear).
  for (const cookie of getSetCookies(upstream.headers)) responseHeaders.append('Set-Cookie', cookie)

  // Keep API redirects on this origin, as nginx's default proxy_redirect does.
  const location = responseHeaders.get('location')
  if (location) {
    const target = new URL(location, apiOrigin + path)
    if (target.origin === apiOrigin) {
      responseHeaders.set('location', '/api' + target.pathname + target.search + target.hash)
    }
  }

  return new Response(upstream.body, {
    status: upstream.status,
    statusText: upstream.statusText,
    headers: responseHeaders,
  })
}

export const onRequest = (context: PagesContext): Promise<Response> =>
  proxyApiRequest(context.request, context.env)
