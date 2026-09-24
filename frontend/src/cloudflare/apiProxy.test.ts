import { afterEach, describe, expect, it, vi } from 'vitest'
import { onRequest, parseApiOrigin, proxyApiRequest, stripApiPrefix } from '../../functions/api/[[path]]'

const API = 'https://api.example.com'
const env = { NOVAQ_API_ORIGIN: API }

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
  it('forwards a GET to the API origin without the /api prefix, keeping the query', async () => {
    const fetchMock = stubFetch(Response.json({ google_sign_in_enabled: true }))
    const response = await onRequest({
      request: new Request('https://novaq.pages.dev/api/auth/config?lang=tl'),
      env,
    })

    expect(fetchMock).toHaveBeenCalledOnce()
    const [url, init] = fetchMock.mock.calls[0]
    expect(url).toBe('https://api.example.com/auth/config?lang=tl')
    expect(init.method).toBe('GET')
    expect(init.body).toBeUndefined()
    expect(init.redirect).toBe('manual')
    expect(response.status).toBe(200)
    expect(response.headers.get('content-type')).toContain('application/json')
    expect(await response.json()).toEqual({ google_sign_in_enabled: true })
  })

  it('forwards method, body, cookies, Origin and CSRF header but drops proxy and cf-* headers', async () => {
    const fetchMock = stubFetch(new Response(null, { status: 204 }))
    const body = JSON.stringify({ name: 'Morning shift' })
    await proxyApiRequest(
      new Request('https://novaq.pages.dev/api/analyses/7', {
        method: 'PATCH',
        body,
        headers: {
          'Content-Type': 'application/json',
          Cookie: 'novaq_session=s1; novaq_csrf=c1',
          Origin: 'https://novaq.pages.dev',
          'X-CSRF-Token': 'c1',
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
    expect(sent.get('origin')).toBe('https://novaq.pages.dev')
    expect(sent.get('content-type')).toBe('application/json')
    expect(sent.get('x-request-id')).toBe('req-123')
    for (const name of ['x-forwarded-for', 'x-real-ip', 'cf-connecting-ip', 'authorization', 'host']) {
      expect(sent.has(name)).toBe(false)
    }
  })

  it('passes multipart upload bytes through unchanged', async () => {
    const fetchMock = stubFetch(Response.json({ id: 1 }, { status: 201 }))
    const form = new FormData()
    form.append('file', new Blob(['time,arrivals\n08:00,12\n'], { type: 'text/csv' }), 'arrivals.csv')
    const original = new Request('https://novaq.pages.dev/api/datasets', { method: 'POST', body: form })
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
      new Request('https://novaq.pages.dev/api/auth/google', { method: 'POST', body: '{}' }),
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
      new Request('https://novaq.pages.dev/api/auth/logout', { method: 'POST' }),
      env,
    )
    expect(response.status).toBe(403)
    expect(await response.json()).toEqual({ detail: 'CSRF token mismatch.' })
  })

  it('rewrites API-origin redirects back under /api and leaves external ones alone', async () => {
    stubFetch(new Response(null, { status: 307, headers: { Location: 'https://api.example.com/analyses/?page=2' } }))
    const internal = await proxyApiRequest(new Request('https://novaq.pages.dev/api/analyses?page=2'), env)
    expect(internal.status).toBe(307)
    expect(internal.headers.get('location')).toBe('/api/analyses/?page=2')

    stubFetch(new Response(null, { status: 302, headers: { Location: 'https://accounts.google.com/o/oauth2' } }))
    const external = await proxyApiRequest(new Request('https://novaq.pages.dev/api/whatever'), env)
    expect(external.headers.get('location')).toBe('https://accounts.google.com/o/oauth2')
  })

  it('fails closed with JSON when the API origin is missing or invalid', async () => {
    const fetchMock = stubFetch(new Response('unused'))
    for (const bad of [{}, { NOVAQ_API_ORIGIN: 'http://api.example.com' }]) {
      const response = await proxyApiRequest(new Request('https://novaq.pages.dev/api/auth/config'), bad)
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
    const response = await proxyApiRequest(new Request('https://novaq.pages.dev/api/health'), env)
    expect(response.status).toBe(502)
    expect(await response.json()).toMatchObject({ code: 'api_unreachable' })
  })
})
