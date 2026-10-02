// Cloudflare Pages Function: same-origin bridge from /api/* to the NovaQ API.
// Mirrors nginx/nginx.conf and the Vite dev proxy: strip the leading /api and
// forward to NOVAQ_API_ORIGIN, keeping cookies and the CSRF header intact.

export interface ApiProxyEnv {
  NOVAQ_API_ORIGIN?: string
  NOVAQ_PROXY_ASSERTION_SECRET?: string
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
  'x-novaq-client-protocol',
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
const encoder = new TextEncoder()

function canonicalClientIp(raw: string | null): string | null {
  if (!raw || raw !== raw.trim() || /[\s,%]/.test(raw)) return null
  if (/^(?:[0-9]+\.){3}[0-9]+$/.test(raw)) {
    const parts = raw.split('.')
    if (parts.some((part) => (part.length > 1 && part.startsWith('0')) || Number(part) > 255)) return null
    return parts.map(Number).join('.')
  }
  if (!raw.includes(':')) return null
  try {
    const parsed = new URL(`http://[${raw}]/`)
    return parsed.hostname.startsWith('[') && parsed.hostname.endsWith(']')
      ? parsed.hostname.slice(1, -1)
      : null
  } catch {
    return null
  }
}

function decodeSecret(raw: string | undefined): Uint8Array | null {
  if (!raw || !/^[A-Za-z0-9_-]{43}$/.test(raw)) return null
  try {
    const bytes = Uint8Array.from(atob(raw.replace(/-/g, '+').replace(/_/g, '/') + '='), (c) => c.charCodeAt(0))
    const canonical = btoa(String.fromCharCode(...bytes)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
    return bytes.length === 32 && canonical === raw ? bytes : null
  } catch {
    return null
  }
}

async function signAssertion(
  headers: Headers, secret: Uint8Array, ip: string, method: string, pathQuery: string,
): Promise<void> {
  const timestamp = Math.floor(Date.now() / 1000).toString()
  const nonce = [...crypto.getRandomValues(new Uint8Array(16))]
    .map((byte) => byte.toString(16).padStart(2, '0')).join('')
  // v1: six fields, LF-separated, UTF-8 encoded, no final LF.
  const payload = `v1\n${timestamp}\n${nonce}\n${ip}\n${method}\n${pathQuery}`
  const key = await crypto.subtle.importKey('raw', Uint8Array.from(secret), { name: 'HMAC', hash: 'SHA-256' }, false, ['sign'])
  const mac = new Uint8Array(await crypto.subtle.sign('HMAC', key, encoder.encode(payload)))
  const signature = btoa(String.fromCharCode(...mac)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
  headers.set('X-NovaQ-Proxy-Version', '1')
  headers.set('X-NovaQ-Proxy-Timestamp', timestamp)
  headers.set('X-NovaQ-Proxy-Nonce', nonce)
  headers.set('X-NovaQ-Proxy-Client-IP', ip)
  headers.set('X-NovaQ-Proxy-Signature', signature)
}

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
  const secret = decodeSecret(env.NOVAQ_PROXY_ASSERTION_SECRET)
  if (!secret) return jsonError(500, 'proxy_secret_unconfigured', 'The API ingress is not configured.')
  // Read Cloudflare's incoming Pages request before making the Render subrequest.
  const clientIp = canonicalClientIp(request.headers.get('CF-Connecting-IP'))
  if (!clientIp) return jsonError(403, 'client_ip_unavailable', 'The caller address is unavailable.')

  const incoming = new URL(request.url)
  const path = stripApiPrefix(incoming.pathname)
  if (path === null) return jsonError(404, 'not_found', 'Not found.')

  const headers = new Headers()
  for (const name of FORWARDED_REQUEST_HEADERS) {
    const value = request.headers.get(name)
    if (value !== null) headers.set(name, value)
  }
  await signAssertion(headers, secret, clientIp, request.method, path + incoming.search)

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
  for (const name of [
    'X-NovaQ-Proxy-Version', 'X-NovaQ-Proxy-Timestamp', 'X-NovaQ-Proxy-Nonce',
    'X-NovaQ-Proxy-Client-IP', 'X-NovaQ-Proxy-Signature',
  ]) responseHeaders.delete(name)
  // Each cookie must stay its own Set-Cookie header (session, CSRF, nonce clear).
  for (const cookie of getSetCookies(upstream.headers)) responseHeaders.append('Set-Cookie', cookie)

  // Keep API redirects on this origin, as nginx's default proxy_redirect does.
  const location = responseHeaders.get('location')
  if (location) {
    let target: URL
    try {
      target = new URL(location, apiOrigin + path)
    } catch {
      return jsonError(502, 'api_redirect_rejected', 'The API returned an invalid redirect.')
    }
    const trusted = new URL(apiOrigin)
    if (
      (target.protocol === 'http:' || target.protocol === 'https:')
      && target.host === trusted.host
      && !target.username && !target.password
    ) {
      responseHeaders.set('location', '/api' + target.pathname + target.search + target.hash)
    } else {
      return jsonError(502, 'api_redirect_rejected', 'The API returned an untrusted redirect.')
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
