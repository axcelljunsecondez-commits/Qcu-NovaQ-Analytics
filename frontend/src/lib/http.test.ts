import { describe, it, expect, vi, beforeEach, afterEach } from 'vitest'
import { http } from './http'

const adapterMock = vi.fn(async (config: { headers: Record<string, string> }) => ({
  data: {},
  status: 200,
  statusText: 'OK',
  headers: {},
  config,
}))

beforeEach(() => {
  adapterMock.mockClear()
  http.defaults.adapter = adapterMock as never
})

afterEach(() => {
  document.cookie = 'novaq_csrf=; expires=Thu, 01 Jan 1970 00:00:00 GMT; path=/'
})

describe('http CSRF interceptor', () => {
  it('attaches X-CSRF-Token to POST when the csrf cookie is present', async () => {
    document.cookie = 'novaq_csrf=test-token'
    await http.post('/anything')
    const config = adapterMock.mock.calls[0][0]
    expect(config.headers['X-CSRF-Token']).toBe('test-token')
  })

  it('sends no X-CSRF-Token on GET', async () => {
    document.cookie = 'novaq_csrf=test-token'
    await http.get('/anything')
    const config = adapterMock.mock.calls[0][0]
    expect(config.headers['X-CSRF-Token']).toBeUndefined()
  })
})
