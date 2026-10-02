/// <reference types="node" />
import { createHmac, webcrypto } from 'node:crypto'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { onRequest, parseApiOrigin, proxyApiRequest, stripApiPrefix } from '../../functions/api/[[path]]'

const API = 'https://api.example.com'
const secret = btoa('s'.repeat(32)).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
const env = { NOVAQ_API_ORIGIN: API, NOVAQ_PROXY_ASSERTION_SECRET: secret }

function pagesRequest(input: string, init?: RequestInit): Request {
  const request = new globalThis.Request(input, init)
  if (!request.headers.has('CF-Connecting-IP')) request.headers.set('CF-Connecting-IP', '198.51.100.8')
  return request
}

beforeEach(() => {
  vi.stubGlobal('crypto', webcrypto)
})

function stubFetch(response: Response) {
  const fetchMock = vi.fn(async (_url: string, _init: RequestInit) => response)
  vi.stubGlobal('fetch', fetchMock)
  return fetchMock
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('parseApiOrigin', () => {
  it('accepts exact HTTPS origins and localhost HTTP', () => {
    expect(parseApiOrigin('https://api.example.com')).toBe('https://api.example.com')
    expect(parseApiOrigin(' https://api.example.com/ ')).toBe('https://api.example.com')
    expect(parseApiOrigin('http://localhost:8000')).toBe('http://localhost:8000')
    expect(parseApiOrigin('http://127.0.0.1:8000')).toBe('http://127.0.0.1:8000')
  })

  it('rejects missing, plain-HTTP, path-bearing or credentialed values', () => {
    expect(parseApiOrigin(undefined)).toBeNull()
    expect(parseApiOrigin('')).toBeNull()
    expect(parseApiOrigin('not a url')).toBeNull()
    expect(parseApiOrigin('http://api.example.com')).toBeNull()
    expect(parseApiOrigin('https://api.example.com/v1')).toBeNull()
    expect(parseApiOrigin('https://api.example.com?x=1')).toBeNull()
    expect(parseApiOrigin('https://user:pw@api.example.com')).toBeNull()
  })
})

describe('stripApiPrefix', () => {
  it('removes only the leading /api segment', () => {
    expect(stripApiPrefix('/api')).toBe('/')
    expect(stripApiPrefix('/api/')).toBe('/')
    expect(stripApiPrefix('/api/auth/config')).toBe('/auth/config')
    expect(stripApiPrefix('/api/api/x')).toBe('/api/x')
    expect(stripApiPrefix('/apiary')).toBeNull()
    expect(stripApiPrefix('/login')).toBeNull()
  })
})

describe('proxyApiRequest', () => {
  it('signs the exact upstream method and path using incoming Cloudflare client IP', async () => {
    const fetchMock = stubFetch(Response.json({ ok: true }, {
      headers: { 'X-NovaQ-Proxy-Signature': 'must-not-escape' },
    }))
    const request = pagesRequest('https://novaq.pages.dev/api/auth/config?lang=tl', {
      headers: {
        'CF-Connecting-IP': '2001:0db8::0001',
        'X-NovaQ-Proxy-Client-IP': '203.0.113.99',
        'X-NovaQ-Proxy-Signature': 'attacker',
        'X-Forwarded-For': '203.0.113.99',
      },
    })
    const response = await proxyApiRequest(request, env)
    const [, init] = fetchMock.mock.calls[0]
    const sent = init.headers as Headers
    expect(sent.get('X-NovaQ-Proxy-Version')).toBe('1')
    expect(sent.get('X-NovaQ-Proxy-Client-IP')).toBe('2001:db8::1')
    expect(sent.has('X-Forwarded-For')).toBe(false)
    expect(sent.get('X-NovaQ-Proxy-Nonce')).toMatch(/^[0-9a-f]{32}$/)
    const payload = [
      'v1', sent.get('X-NovaQ-Proxy-Timestamp'), sent.get('X-NovaQ-Proxy-Nonce'),
      '2001:db8::1', 'GET', '/auth/config?lang=tl',
    ].join('\n')
    const expected = createHmac('sha256', Buffer.from('s'.repeat(32))).update(payload).digest('base64url')
    expect(sent.get('X-NovaQ-Proxy-Signature')).toBe(expected)
    expect(response.headers.has('X-NovaQ-Proxy-Signature')).toBe(false)
    expect(response.headers.has('X-NovaQ-Proxy-Client-IP')).toBe(false)
  })

  it('fails closed when the signing secret or ingress IP is unavailable', async () => {
    const fetchMock = stubFetch(Response.json({ ok: true }))
    const noSecret = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/health'), {
      NOVAQ_API_ORIGIN: API,
    })
    expect(noSecret.status).toBe(500)
    expect((await noSecret.json() as { code: string }).code).toBe('proxy_secret_unconfigured')
    const noIp = await proxyApiRequest(new globalThis.Request('https://novaq.pages.dev/api/health'), env)
    expect(noIp.status).toBe(403)
    for (const bad of ['unknown', '203.0.113.999', '198.51.100.1, 203.0.113.2', 'fe80::1%eth0']) {
      const denied = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/health', {
        headers: { 'CF-Connecting-IP': bad },
      }), env)
      expect(denied.status).toBe(403)
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('forwards a GET to the API origin without the /api prefix, keeping the query', async () => {
    const fetchMock = stubFetch(Response.json({ google_sign_in_enabled: true }))
    const response = await onRequest({
      request: pagesRequest('https://novaq.pages.dev/api/auth/config?lang=tl'),
      env,
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.example.com/auth/config?lang=tl')
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
    expect(init.redirect).toBe('manual')
    expect((init.headers as Headers).get('X-NovaQ-Proxy-Client-IP')).toBe('198.51.100.8')
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toContain('application/json')
    expect(await response.json()).toEqual({ google_sign_in_enabled: true })
  })

  it('forwards method, body, cookies, Origin and CSRF header but drops proxy and cf-* headers', async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }))
    const body = JSON.stringify({ name: 'Morning shift' })
    await proxyApiRequest(
      pagesRequest('https://novaq.pages.dev/api/analyses/7', {
        method: 'PATCH',
        body,
        headers: {
          'Content-Type': 'application/json',
          Cookie: 'novaq_session=s1; novaq_csrf=c1',
          Origin: 'https://novaq.pages.dev',
          'X-CSRF-Token': 'c1',
          'X-NovaQ-Client-Protocol': '2',
          'X-Request-ID': 'req-123',
          'X-Forwarded-For': '203.0.113.9',
          'X-Real-IP': '203.0.113.9',
          'CF-Connecting-IP': '198.51.100.4',
          Authorization: 'Bearer spoof',
        },
      }),
      env,
    )

    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.example.com/analyses/7')
    expect(init.method).toBe('PATCH')
    expect(new TextDecoder().decode(init.body as ArrayBuffer)).toBe(body)
    const sent = init.headers as Headers
    expect(sent.get('cookie')).toBe('novaq_session=s1; novaq_csrf=c1')
    expect(sent.get('x-csrf-token')).toBe('c1')
    expect(sent.get('x-novaq-client-protocol')).toBe('2')
    expect(sent.get('origin')).toBe('https://novaq.pages.dev')
    expect(sent.get('content-type')).toBe('application/json')
    expect(sent.get('x-request-id')).toBe('req-123')
    for (const name of ['x-forwarded-for', 'x-real-ip', 'cf-connecting-ip', 'authorization', 'host']) {
      expect(sent.has(name)).toBe(false)
    }
  })

  it('never synthesizes or repairs the client protocol header', async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }))
    const endpoint = 'https://novaq.pages.dev/api/scenarios'

    await proxyApiRequest(pagesRequest(endpoint), env)
    await proxyApiRequest(pagesRequest(endpoint, {
      headers: { 'X-NovaQ-Client-Protocol': '1' },
    }), env)

    const mixed = new Headers()
    mixed.append('X-NovaQ-Client-Protocol', '2')
    mixed.append('X-NovaQ-Client-Protocol', '1')
    const mixedRequest = pagesRequest(endpoint, { headers: mixed })
    await proxyApiRequest(mixedRequest, env)

    const repeated = new Headers()
    repeated.append('X-NovaQ-Client-Protocol', '2')
    repeated.append('X-NovaQ-Client-Protocol', '2')
    const repeatedRequest = pagesRequest(endpoint, { headers: repeated })
    await proxyApiRequest(repeatedRequest, env)

    expect(fetchMock).toHaveBeenCalledTimes(4)
    const sent = fetchMock.mock.calls.map(([, init]) => init.headers as Headers)
    expect(sent[0].has('x-novaq-client-protocol')).toBe(false)
    expect(sent[1].get('x-novaq-client-protocol')).toBe('1')
    expect(sent[2].get('x-novaq-client-protocol')).toBe(mixedRequest.headers.get('x-novaq-client-protocol'))
    expect(sent[2].get('x-novaq-client-protocol')).toBe('2, 1')
    expect(sent[3].get('x-novaq-client-protocol')).toBe(repeatedRequest.headers.get('x-novaq-client-protocol'))
    expect(sent[3].get('x-novaq-client-protocol')).toBe('2, 2')
    for (const headers of sent.slice(1)) {
      expect(headers.get('x-novaq-client-protocol')).not.toBe('2')
    }
  })

  it('passes multipart upload bytes through unchanged', async () => {
    const fetchMock = stubFetch(Response.json({ id: 1 }, { status: 201 }))
    const form = new FormData()
    form.append('file', new Blob(['time,arrivals\n08:00,12\n'], { type: 'text/csv' }), 'arrivals.csv')
    const original = pagesRequest('https://novaq.pages.dev/api/datasets', { method: 'POST', body: form })
    const expected = new Uint8Array(await original.clone().arrayBuffer())

    const response = await proxyApiRequest(original, env)

    const [, init] = fetchMock.mock.calls[0]
    expect(new Uint8Array(init.body as ArrayBuffer)).toEqual(expected)
    expect((init.headers as Headers).get('content-type')).toMatch(/^multipart\/form-data; boundary=/)
    expect(response.status).toBe(201)
  })

  it('keeps every Set-Cookie header separate (session, CSRF and nonce clear)', async () => {
    const upstreamHeaders = new Headers({ 'Content-Type': 'application/json' })
    upstreamHeaders.append('Set-Cookie', 'novaq_session=s2; HttpOnly; Max-Age=28800; Path=/; SameSite=lax; Secure')
    upstreamHeaders.append('Set-Cookie', 'novaq_csrf=c2; Max-Age=28800; Path=/; SameSite=lax; Secure')
    upstreamHeaders.append('Set-Cookie', 'novaq_google_nonce=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/')
    stubFetch(new Response('{"user":{}}', { status: 200, headers: upstreamHeaders }))

    const response = await proxyApiRequest(
      pagesRequest('https://novaq.pages.dev/api/auth/google', { method: 'POST', body: '{}' }),
      env,
    )

    expect(response.headers.getSetCookie()).toEqual([
      'novaq_session=s2; HttpOnly; Max-Age=28800; Path=/; SameSite=lax; Secure',
      'novaq_csrf=c2; Max-Age=28800; Path=/; SameSite=lax; Secure',
      'novaq_google_nonce=""; expires=Thu, 01 Jan 1970 00:00:00 GMT; Max-Age=0; Path=/',
    ])
  })

  it('passes API error statuses and bodies through untouched', async () => {
    stubFetch(Response.json({ detail: 'CSRF token mismatch.' }, { status: 403 }))
    const response = await proxyApiRequest(
      pagesRequest('https://novaq.pages.dev/api/auth/logout', { method: 'POST' }),
      env,
    )
    expect(response.status).toBe(403)
    expect(await response.json()).toEqual({ detail: 'CSRF token mismatch.' })
  })

  it('preserves a protocol-fence 403 body and cache headers', async () => {
    const body = {
      code: 'client_update_required',
      detail: 'NovaQ has been updated. Reload the application.',
      request_id: 'req-403',
    }
    stubFetch(Response.json(body, {
      status: 403,
      headers: {
        'Cache-Control': 'private, no-store',
        Vary: 'X-NovaQ-Client-Protocol',
        'X-Request-ID': 'req-403',
      },
    }))

    const response = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/scenarios'), env)
    expect(response.status).toBe(403)
    expect(response.headers.get('cache-control')).toBe('private, no-store')
    expect(response.headers.get('vary')).toBe('X-NovaQ-Client-Protocol')
    expect(response.headers.get('x-request-id')).toBe('req-403')
    expect(await response.json()).toEqual(body)
  })

  it('rewrites API-origin redirects back under /api and rejects external redirects', async () => {
    stubFetch(new Response(null, { status: 307, headers: { Location: 'https://api.example.com/analyses/?page=2' } }))
    const internal = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/analyses?page=2'), env)
    expect(internal.status).toBe(307)
    expect(internal.headers.get('location')).toBe('/api/analyses/?page=2')

    stubFetch(new Response(null, { status: 302, headers: { Location: 'https://accounts.google.com/o/oauth2' } }))
    const external = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/whatever'), env)
    expect(external.status).toBe(502)
    expect(external.headers.has('location')).toBe(false)
  })

  it('rewrites internal HTTP redirects to the public HTTPS Pages route without an open redirect', async () => {
    stubFetch(new Response(null, {
      status: 307, headers: { Location: 'http://api.example.com/health/?next=%2Fready' },
    }))
    const request = pagesRequest('https://novaq.pages.dev/api/health/?next=%2Fready')
    const response = await proxyApiRequest(request, env)
    expect(response.headers.get('location')).toBe('/api/health/?next=%2Fready')
    expect(new URL(response.headers.get('location')!, request.url).origin).toBe('https://novaq.pages.dev')

    stubFetch(new Response(null, {
      status: 307, headers: { Location: 'http://api.example.com.attacker.invalid/steal' },
    }))
    const malicious = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/health/'), env)
    expect(malicious.status).toBe(502)
    expect(malicious.headers.has('location')).toBe(false)

    stubFetch(new Response(null, { status: 307, headers: { Location: 'http://[' } }))
    const malformed = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/health/'), env)
    expect(malformed.status).toBe(502)
  })

  it('fails closed with JSON when the API origin is missing or invalid', async () => {
    const fetchMock = stubFetch(new Response('unused'))
    for (const bad of [{}, { NOVAQ_API_ORIGIN: 'http://api.example.com' }]) {
      const response = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/auth/config'), bad)
      expect(response.status).toBe(500)
      expect(response.headers.get('content-type')).toBe('application/json')
      expect(await response.json()).toMatchObject({ code: 'api_origin_unconfigured' })
    }
    expect(fetchMock).not.toHaveBeenCalled()
  })

  it('returns a JSON 502 when the API cannot be reached', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => {
      throw new TypeError('network down')
    }))
    const response = await proxyApiRequest(pagesRequest('https://novaq.pages.dev/api/health'), env)
    expect(response.status).toBe(502)
    expect(await response.json()).toMatchObject({ code: 'api_unreachable' })
  })
})
